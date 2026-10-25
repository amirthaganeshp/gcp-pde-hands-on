"""CDC: turning a change log into current state, correctly.

Datastream and Database Migration Service both deliver CHANGE EVENTS,
not rows: an append-only stream of inserts, updates and deletes. Getting
current state out of that stream is the consumer's job, and it is where
CDC pipelines go quietly wrong - the naive version produces a table that
looks entirely plausible and is not correct.

  1. What a change stream actually contains
  2. The naive merge - apply events in arrival order
  3. Why it is wrong: out-of-order, duplicates, tombstones
  4. The correct merge - latest version per key, deletes honoured
  5. Append-only vs merged: two valid targets, different questions

EXECUTED IN FULL. Pure Python over a synthetic change stream built from
the trip data, with the three real-world defects injected deliberately.

Run:
    python 00_setup/make_data.py       # once
    python 07_migration_cdc/01_datastream/cdc_patterns.py

Guide reference: Success Guide pp. 27-30; Ultimate Edition section 2.3.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRIPS = REPO / "data" / "trips.csv"

SEED = 42
N_KEYS = 500              # distinct rows in the source table
DUP_RATE = 0.08           # at-least-once delivery duplicates ~8%
REORDER_WINDOW = 25       # how far an event can arrive out of order


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


# ============================================ 1. the change stream
def build_stream(rng: random.Random) -> tuple[list[dict], dict]:
    """Build a change stream, and the TRUTH it should produce.

    Every event carries:
      op   - INSERT / UPDATE / DELETE
      lsn  - the source's monotonic sequence number (log sequence
             number, SCN, binlog position - every engine has one)
    """
    rows = []
    with TRIPS.open(encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f)):
            if i >= N_KEYS:
                break
            rows.append(r)

    events: list[dict] = []
    truth: dict[str, dict | None] = {}
    lsn = 0

    for r in rows:                                   # initial load
        lsn += 1
        events.append({"op": "INSERT", "lsn": lsn, "trip_id": r["trip_id"],
                       "duration_min": float(r["duration_min"]),
                       "station": r["start_station"]})
        truth[r["trip_id"]] = {"duration_min": float(r["duration_min"]),
                               "station": r["start_station"]}

    for r in rows:                                   # then changes
        roll = rng.random()
        if roll < 0.30:                              # correction
            lsn += 1
            new = round(float(r["duration_min"]) + rng.uniform(1, 5), 2)
            events.append({"op": "UPDATE", "lsn": lsn,
                           "trip_id": r["trip_id"], "duration_min": new,
                           "station": r["start_station"]})
            truth[r["trip_id"]] = {"duration_min": new,
                                   "station": r["start_station"]}
        elif roll < 0.40:                            # retraction
            lsn += 1
            events.append({"op": "DELETE", "lsn": lsn,
                           "trip_id": r["trip_id"], "duration_min": None,
                           "station": None})
            truth[r["trip_id"]] = None

    # --- now inject the three things a real stream does to you ---
    # (a) DUPLICATES: delivery is at-least-once
    dups = [dict(e) for e in events if rng.random() < DUP_RATE]
    events.extend(dups)

    # (b) OUT OF ORDER: parallel readers, retries, partitioned topics
    for i in range(len(events)):
        j = min(len(events) - 1, i + rng.randrange(0, REORDER_WINDOW))
        events[i], events[j] = events[j], events[i]

    return events, {k: v for k, v in truth.items()}


def describe(events: list[dict], truth: dict) -> dict:
    banner("1. What a change stream contains")

    ops = {}
    for e in events:
        ops[e["op"]] = ops.get(e["op"], 0) + 1
    live = sum(1 for v in truth.values() if v is not None)
    deleted = sum(1 for v in truth.values() if v is None)

    print(f"  {len(events):,} change events over {len(truth):,} distinct keys\n")
    for op in ("INSERT", "UPDATE", "DELETE"):
        print(f"    {op:<8} {ops.get(op, 0):>6,}")

    print(f"\n  TRUE final state: {live:,} live rows, {deleted:,} deleted")

    print("\n  Every event carries an LSN - the source's monotonic sequence")
    print("  number (binlog position in MySQL, SCN in Oracle, LSN in")
    print("  Postgres). **That number, not arrival time, is the ordering")
    print("  that matters**, and it is the whole basis of a correct merge.")

    print("\n  This stream has had three real defects injected:")
    print(f"    - DUPLICATES      ~{DUP_RATE:.0%}, because delivery is at-least-once")
    print(f"    - OUT OF ORDER    up to {REORDER_WINDOW} positions")
    print("    - TOMBSTONES      deletes that must remove, not ignore")
    return {"events": len(events), "keys": len(truth),
            "live": live, "deleted": deleted, "ops": ops}


# ============================================ 2-3. the naive merge
def naive_merge(events: list[dict]) -> dict:
    """Apply events in ARRIVAL order. This is what people write first."""
    state: dict[str, dict] = {}
    for e in events:
        if e["op"] == "DELETE":
            state.pop(e["trip_id"], None)
        else:
            state[e["trip_id"]] = {"duration_min": e["duration_min"],
                                   "station": e["station"]}
    return state


# ============================================ 4. the correct merge
def correct_merge(events: list[dict]) -> dict:
    """Latest version PER KEY by LSN, with deletes honoured.

    Three properties, and all three are needed:
      1. group by key, take max LSN   -> handles out-of-order
      2. dedupe on (key, lsn)          -> handles at-least-once
      3. a winning DELETE removes      -> handles tombstones
    """
    latest: dict[str, dict] = {}
    for e in events:
        prev = latest.get(e["trip_id"])
        if prev is None or e["lsn"] > prev["lsn"]:
            latest[e["trip_id"]] = e

    return {k: {"duration_min": e["duration_min"], "station": e["station"]}
            for k, e in latest.items() if e["op"] != "DELETE"}


def compare(naive: dict, correct: dict, truth: dict) -> dict:
    banner("2-4. Naive vs correct, against known truth")

    expected = {k: v for k, v in truth.items() if v is not None}

    def score(got: dict) -> dict:
        missing = set(expected) - set(got)
        extra = set(got) - set(expected)
        wrong = {k for k in set(got) & set(expected)
                 if abs(got[k]["duration_min"]
                        - expected[k]["duration_min"]) > 1e-9}
        return {"rows": len(got), "missing": len(missing),
                "extra": len(extra), "wrong": len(wrong),
                "correct": len(got) - len(extra) - len(wrong)}

    n, c = score(naive), score(correct)

    print(f"  truth: {len(expected):,} live rows\n")
    print(f"  {'merge':<10} {'rows':>7} {'missing':>9} "
          f"{'resurrected':>13} {'stale value':>13} {'correct':>9}")
    print("  " + "-" * 70)
    for label, s in (("naive", n), ("correct", c)):
        print(f"  {label:<10} {s['rows']:>7,} {s['missing']:>9,} "
              f"{s['extra']:>13,} {s['wrong']:>13,} {s['correct']:>9,}")

    print(f"\n  The naive merge got {n['wrong']:,} rows WRONG and "
          f"resurrected {n['extra']:,}")
    print("  deleted rows - and its row count is close enough to the truth")
    print("  that a count check would pass.")

    print("\n  **That is what makes this dangerous.** The table is the right")
    print("  shape, the totals are nearly right, and the individual values")
    print("  are stale. Nothing errors.")

    print("\n  Three defects, three consequences:")
    print("    OUT OF ORDER  an older UPDATE arrives last and overwrites a")
    print("                  newer one - the stale values above")
    print("    DUPLICATES    replaying an old event re-applies it")
    print("    TOMBSTONES    a DELETE arriving before its UPDATE gets")
    print("                  undone - the resurrected rows above")
    return {"naive": n, "correct": c}


# ============================================ 5. the two targets
def two_targets() -> None:
    banner("5. Append-only vs merged - two valid targets")

    print(f"  {'':<16} {'append-only log':<26} merged current state")
    print("  " + "-" * 70)
    rows = [
        ("holds", "every change, forever", "one row per key, latest"),
        ("answers", "what did it look like then?", "what is it now?"),
        ("write cost", "cheap - pure append", "MERGE, or a view over the log"),
        ("storage", "grows without bound", "bounded by key count"),
        ("audit", "complete history", "none"),
    ]
    for a, b, c in rows:
        print(f"  {a:<16} {b:<26} {c}")

    print("\n  **Datastream writes the append-only form.** Into BigQuery it")
    print("  can also maintain the merged form for you; into GCS you get")
    print("  the log and the merge is yours.")

    print("\n  The usual production answer is BOTH: land the raw log once,")
    print("  and build current state from it as a view or a scheduled MERGE.")
    print("  The log is the source of truth and can be replayed; the merged")
    print("  table is a derived convenience. Merging on arrival and keeping")
    print("  nothing means a bug in the merge is unrecoverable.")

    print("\n  The BigQuery MERGE for the correct version is in")
    print("  ../../03_bigquery/01_bigquery/bigquery_patterns.sql section 8 -")
    print("  keyed on a BUSINESS id, which is what makes it idempotent and")
    print("  safe to re-run after the at-least-once delivery in")
    print("  01_ingestion/01_pubsub.")


def main() -> None:
    if not TRIPS.exists():
        raise SystemExit(f"  {TRIPS} not found - run 00_setup/make_data.py first.")

    print("=" * 72)
    print("  CDC - change log to current state".center(72))
    print("=" * 72)

    rng = random.Random(SEED)
    events, truth = build_stream(rng)

    d = describe(events, truth)
    naive = naive_merge(events)
    correct = correct_merge(events)
    r = compare(naive, correct, truth)
    two_targets()

    banner("Summary - measured against known truth")
    print(f"  - {d['events']:,} events, {d['keys']:,} keys, "
          f"{d['live']:,} live rows in truth")
    print(f"  - naive merge   : {r['naive']['wrong']:,} stale values, "
          f"{r['naive']['extra']:,} resurrected deletes")
    print(f"  - correct merge : {r['correct']['wrong']:,} stale, "
          f"{r['correct']['extra']:,} resurrected")
    print("\n  Order by the source's LSN, not by arrival. Dedupe on")
    print("  (key, lsn). Let a winning DELETE remove the row. Miss any one")
    print("  of the three and the result still looks like a table.")


if __name__ == "__main__":
    main()
