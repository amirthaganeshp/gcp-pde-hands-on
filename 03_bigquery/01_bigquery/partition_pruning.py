"""Why BigQuery costs what it costs: bytes scanned, measured.

BigQuery bills on-demand queries by BYTES SCANNED, so its three cost
levers are all the same question - how much of the table can the engine
avoid reading?

    1. COLUMN PROJECTION   read 2 columns instead of 10
    2. PARTITION PRUNING   skip whole date partitions
    3. BLOCK PRUNING       skip blocks whose min/max cannot match
                           (this is what CLUSTERING buys you)

** THIS IS A SIMULATION, AND THE LABEL MATTERS. **

There is no local BigQuery emulator, so this measures Apache Parquet
instead. That is a fair analogue rather than a fudge: Parquet is
columnar, stores row groups with per-column min/max statistics, and
prunes them on a predicate - which is mechanically what BigQuery does
with its blocks. The MECHANISM transfers; the numbers do not. Real
BigQuery has different block sizes, its own encodings, and a minimum
10 MB billed per table scanned.

Real, unmodified BigQuery SQL for all of this is in
bigquery_patterns.sql - correct, and never submitted.

Run:
    python 00_setup/make_data.py           # once
    python 03_bigquery/01_bigquery/partition_pruning.py

Guide reference: Success Guide pp. 34-39; Ultimate Edition section 3.4.
"""

from __future__ import annotations

import csv
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[2]
TRIPS = REPO / "data" / "trips.csv"
WORK = REPO / "outputs" / "bq_sim"

FIELDS = ["trip_id", "event_time", "processing_time", "lag_seconds",
          "start_station", "end_station", "bike_type", "duration_min",
          "distance_km", "member"]


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:,.1f} {unit}"
        n /= 1024
    return f"{n:,.1f} TB"


def load_table() -> pa.Table:
    cols: dict[str, list] = {f: [] for f in FIELDS}
    cols["trip_date"] = []
    with TRIPS.open(encoding="utf-8") as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            d = dict(zip(FIELDS, row))
            for k in FIELDS:
                cols[k].append(d[k])
            cols["trip_date"].append(d["event_time"][:10])

    return pa.table({
        "trip_id": pa.array(cols["trip_id"]),
        "trip_date": pa.array(cols["trip_date"]),
        "start_station": pa.array(cols["start_station"]),
        "end_station": pa.array(cols["end_station"]),
        "bike_type": pa.array(cols["bike_type"]),
        "duration_min": pa.array([float(x) for x in cols["duration_min"]]),
        "distance_km": pa.array([float(x) for x in cols["distance_km"]]),
        "member": pa.array([x == "True" for x in cols["member"]]),
        "event_time": pa.array(cols["event_time"]),
        "lag_seconds": pa.array([float(x) for x in cols["lag_seconds"]]),
    })


def dir_bytes(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*.parquet"))


# ============================================ 1. column projection
def column_projection(table: pa.Table) -> dict:
    banner("1. Column projection - the cost of SELECT *")

    flat = WORK / "flat"
    shutil.rmtree(flat, ignore_errors=True)
    flat.mkdir(parents=True)
    pq.write_table(table, flat / "trips.parquet")

    pf = pq.ParquetFile(flat / "trips.parquet")
    total = (flat / "trips.parquet").stat().st_size

    # Per-column compressed size, straight from the file's own metadata.
    sizes: dict[str, int] = {}
    md = pf.metadata
    for rg in range(md.num_row_groups):
        for c in range(md.num_columns):
            col = md.row_group(rg).column(c)
            name = col.path_in_schema
            sizes[name] = sizes.get(name, 0) + col.total_compressed_size

    print(f"  {table.num_rows:,} rows, {md.num_columns} columns, "
          f"{human(total)} on disk\n")
    print(f"  {'column':<18} {'bytes':>12} {'% of table':>12}")
    print("  " + "-" * 46)
    for name, b in sorted(sizes.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<18} {human(b):>12} {b / total:>11.1%}")

    two = sizes["trip_date"] + sizes["duration_min"]
    print(f"\n  SELECT *                       -> {human(total)}  (100.0%)")
    print(f"  SELECT trip_date, duration_min -> {human(two)}  "
          f"({two / total:.1%})")
    print(f"  saving: {total / two:.1f}x")

    print("\n  **Columnar storage is why `SELECT *` is a cost bug, not a")
    print("  style preference.** A column you do not name is a column that is")
    print("  never read off disk - and on BigQuery, never billed.")
    print("\n  Note trip_id is the most expensive column here: it is unique,")
    print("  so it compresses worst. High-cardinality identifiers are exactly")
    print("  the columns you least want in a `SELECT *`.")
    return {"total": total, "two_cols": two, "sizes": sizes}


# ============================================ 2. partition pruning
def partition_pruning(table: pa.Table) -> dict:
    banner("2. Partition pruning - skipping whole days")

    part = WORK / "partitioned"
    shutil.rmtree(part, ignore_errors=True)
    pq.write_to_dataset(table, root_path=str(part),
                        partition_cols=["trip_date"])

    total = dir_bytes(part)
    days = sorted(p.name for p in part.iterdir() if p.is_dir())
    print(f"  written as {len(days)} partitions, one per day, "
          f"{human(total)} total")

    dataset = ds.dataset(str(part), format="parquet", partitioning="hive")

    def scanned(expr) -> int:
        """Bytes in the files a scan would actually open."""
        if expr is None:
            return total
        files = dataset.to_table(filter=expr, columns=["trip_id"])
        # Count the partition dirs the filter admits, then sum their bytes.
        matched = dataset.to_table(filter=expr, columns=["trip_date"])
        wanted = set(matched.column("trip_date").to_pylist())
        return sum(f.stat().st_size
                   for d in part.iterdir() if d.is_dir()
                   and d.name.split("=")[1] in {str(w) for w in wanted}
                   for f in d.rglob("*.parquet"))

    one_day = days[len(days) // 2].split("=")[1]
    three = {d.split("=")[1] for d in days[:3]}

    no_filter = total
    single = scanned(pc.field("trip_date") == one_day)
    triple = scanned(pc.field("trip_date").isin(list(three)))

    print(f"\n  {'query':<42} {'bytes scanned':>14} {'vs full':>9}")
    print("  " + "-" * 68)
    print(f"  {'no date filter':<42} {human(no_filter):>14} {'1.0x':>9}")
    print(f"  {'WHERE trip_date = one day':<42} {human(single):>14} "
          f"{no_filter / max(single, 1):>8.1f}x")
    print(f"  {'WHERE trip_date IN (3 days)':<42} {human(triple):>14} "
          f"{no_filter / max(triple, 1):>8.1f}x")

    print(f"\n  **A partition the filter excludes is never opened.** One day")
    print(f"  out of {len(days)} costs roughly 1/{len(days)} of the table.")

    print("\n  Two things that silently break this on BigQuery:")
    print("    - a filter the engine cannot evaluate before reading, e.g.")
    print("      wrapping the partition column in a function, or comparing")
    print("      it to a subquery result. The query still works; it just")
    print("      scans everything.")
    print("    - no filter at all. `require_partition_filter = true` on the")
    print("      table turns that from a large bill into an error, and is")
    print("      the single most effective cost control BigQuery offers.")
    return {"total": no_filter, "one_day": single, "three_days": triple,
            "n_partitions": len(days)}


# ============================================ 3. block pruning
def block_pruning(table: pa.Table) -> dict:
    banner("3. Block pruning - what CLUSTERING actually buys")

    results: dict[str, dict] = {}

    for label, sort in (("unclustered", False), ("clustered", True)):
        d = WORK / label
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)

        t = table.sort_by([("start_station", "ascending")]) if sort else table
        # Small row groups so the effect is visible at this scale;
        # BigQuery's blocks are far larger and chosen for you.
        pq.write_table(t, d / "trips.parquet", row_group_size=2000)

        pf = pq.ParquetFile(d / "trips.parquet")
        md = pf.metadata
        col_idx = [md.schema.column(i).name
                   for i in range(md.num_columns)].index("start_station")

        target = "ST03"
        hit, total_rg, bytes_hit, bytes_all = 0, md.num_row_groups, 0, 0
        for rg in range(md.num_row_groups):
            g = md.row_group(rg)
            stats = g.column(col_idx).statistics
            rg_bytes = sum(g.column(c).total_compressed_size
                           for c in range(md.num_columns))
            bytes_all += rg_bytes
            if stats is None or (stats.min <= target <= stats.max):
                hit += 1
                bytes_hit += rg_bytes

        results[label] = {"row_groups": total_rg, "hit": hit,
                          "bytes_hit": bytes_hit, "bytes_all": bytes_all}

    print(f"  50,000 rows in row groups of 2,000, filtering "
          f"start_station = 'ST03'.\n")
    print(f"  {'layout':<14} {'blocks':>8} {'blocks read':>12} "
          f"{'bytes read':>13} {'vs full':>9}")
    print("  " + "-" * 62)
    for label in ("unclustered", "clustered"):
        r = results[label]
        print(f"  {label:<14} {r['row_groups']:>8} {r['hit']:>12} "
              f"{human(r['bytes_hit']):>13} "
              f"{r['bytes_all'] / max(r['bytes_hit'], 1):>8.1f}x")

    u, c = results["unclustered"], results["clustered"]
    print(f"\n  **Clustering does not filter rows - it SORTS them, so that")
    print(f"  most blocks can be ruled out by their min/max alone.**")
    print(f"  Unclustered, 'ST03' could be in any block: {u['hit']} of "
          f"{u['row_groups']} had to be read.")
    print(f"  Clustered, it is confined to {c['hit']}.")

    print("\n  That is also why CLUSTER ORDER MATTERS. Blocks are sorted by")
    print("  the first column, then the second within it. A filter on the")
    print("  second column alone prunes far less - so order the cluster keys")
    print("  by how often you filter on them, most-filtered first.")

    print("\n  And why clustering is NOT partitioning: partitions are")
    print("  physical directories with hard boundaries and a 4,000-partition")
    print("  limit; clustering is an ordering with soft, statistical")
    print("  boundaries and no limit on distinct values. Partition on a")
    print("  low-cardinality column you always filter by - usually a date -")
    print("  and cluster on the high-cardinality ones.")
    return results


def main() -> None:
    if not TRIPS.exists():
        raise SystemExit(f"  {TRIPS} not found - run 00_setup/make_data.py first.")

    WORK.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("  BIGQUERY COST MECHANICS - bytes scanned, measured".center(72))
    print("=" * 72)
    print("\n  SIMULATION: this measures Apache Parquet, not BigQuery.")
    print("  Both are columnar with per-block min/max statistics, so the")
    print("  MECHANISM is the same and the numbers are not. Real BigQuery")
    print("  uses larger blocks, its own encodings, and bills a 10 MB")
    print("  minimum per table scanned.")

    table = load_table()
    a = column_projection(table)
    b = partition_pruning(table)
    c = block_pruning(table)

    banner("Summary - three levers, one question")
    print(f"  1. column projection : {a['total'] / a['two_cols']:.1f}x less "
          f"read for 2 columns instead of 10")
    print(f"  2. partition pruning : {b['total'] / max(b['one_day'], 1):.1f}x "
          f"less for 1 day of {b['n_partitions']}")
    print(f"  3. block pruning     : "
          f"{c['clustered']['bytes_all'] / max(c['clustered']['bytes_hit'], 1):.1f}x "
          f"less when clustered, vs "
          f"{c['unclustered']['bytes_all'] / max(c['unclustered']['bytes_hit'], 1):.1f}x "
          f"when not")

    print("\n  All three are the same question - how much can the engine")
    print("  avoid reading? On-demand BigQuery bills exactly that, so the")
    print("  three multiply: a narrow SELECT on a filtered partition of a")
    print("  well-clustered table can be orders of magnitude cheaper than")
    print("  the SELECT * that returns the same answer.")

    print("\n  Real SQL for all of this: bigquery_patterns.sql (never run).")


if __name__ == "__main__":
    main()
