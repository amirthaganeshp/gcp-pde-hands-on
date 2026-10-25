"""Bigtable row-key design: the one thing the exam really tests.

Bigtable has no secondary indexes, no joins and one index - THE ROW KEY.
Every access pattern you will ever have must be expressible as a row-key
prefix or range scan, so the key is not a detail of the schema: it IS
the schema, and it cannot be changed without rewriting the table.

  1. The model - what a Bigtable row actually is
  2. Row keys are SORTED, which is why prefixes work
  3. HOTSPOTTING - measured, on four key designs
  4. Reads: point, prefix, range - and what each costs
  5. The design rules, derived from the measurements

EXECUTED IN FULL against the local Bigtable emulator, which this file
starts and stops itself.

Run:
    python 06_storage_decisions/06_nosql/01_bigtable/row_key_design.py

Guide reference: Success Guide pp. 30-33; Ultimate Edition section 3.3.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import os
import signal
import shutil
import socket
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TRIPS = REPO / "data" / "trips.csv"

PROJECT, INSTANCE, TABLE = "local-demo", "demo-instance", "trips"
EMULATOR_PORT = 8086
CF = "t"                                  # column family

# Bigtable serves ranges of the sorted key space from TABLETS. Real
# Bigtable splits them dynamically; this is the number of equal slices
# used here to make load distribution measurable.
N_TABLETS = 8


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


def find_gcloud() -> str:
    """WSL puts the Windows PATH on the Linux PATH - refuse /mnt/c."""
    if os.path.exists("/usr/bin/gcloud"):
        return "/usr/bin/gcloud"
    found = shutil.which("gcloud")
    if found and found.startswith("/mnt/"):
        raise RuntimeError(
            f"only a Windows gcloud is on PATH ({found}); install the Linux "
            "one:\n    sudo apt-get install -y google-cloud-cli "
            "google-cloud-cli-bigtable-emulator")
    if not found:
        raise RuntimeError(
            "gcloud not found. Install:\n    sudo apt-get install -y "
            "google-cloud-cli google-cloud-cli-bigtable-emulator")
    return found


def _stop_emulator(proc, port: int) -> None:
    """Stop the emulator - the whole PROCESS GROUP, not just the wrapper.

    THE BUG THIS FIXES, found by running the repo's full run-list:
    `gcloud beta emulators ... start` is a WRAPPER that spawns the actual
    emulator as a child (java, or a Go binary for Bigtable). Calling
    proc.terminate() kills only the wrapper and ORPHANS the child, which
    keeps holding the port. The run-list left five such orphans behind,
    some of them running for hours - while every README claimed each
    script "starts and stops its own emulator".

    start_new_session=True puts the wrapper in its own process group so the
    whole group can be signalled here.
    """
    with contextlib.suppress(Exception):
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    with contextlib.suppress(Exception):
        proc.wait(timeout=10)

    # If the port is still held, the group ignored SIGTERM. Escalate.
    with contextlib.closing(socket.socket()) as s:
        s.settimeout(0.5)
        if s.connect_ex(("127.0.0.1", port)) == 0:
            with contextlib.suppress(Exception):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


@contextlib.contextmanager
def emulator(port: int = EMULATOR_PORT):
    gcloud = find_gcloud()
    with contextlib.closing(socket.socket()) as s:
        s.settimeout(1.0)
        if s.connect_ex(("127.0.0.1", port)) == 0:
            print(f"  Emulator already on :{port} - reusing.\n")
            os.environ["BIGTABLE_EMULATOR_HOST"] = f"localhost:{port}"
            yield
            return

    print(f"  Starting Bigtable emulator on :{port} ...")
    proc = subprocess.Popen(
        [gcloud, "beta", "emulators", "bigtable", "start",
         f"--host-port=localhost:{port}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)   # own process group - see _stop_emulator
    os.environ["BIGTABLE_EMULATOR_HOST"] = f"localhost:{port}"

    for _ in range(60):
        with contextlib.closing(socket.socket()) as s:
            s.settimeout(1.0)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError("bigtable emulator did not start within 30 s")

    print("  Emulator up.\n")
    try:
        yield
    finally:
        _stop_emulator(proc, port)
        print("\n  Emulator stopped.")


def load_trips(limit: int = 4000) -> list[dict]:
    rows = []
    with TRIPS.open(encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f)):
            if i >= limit:
                break
            rows.append(r)
    return rows


# ============================================ key designs
def key_sequential(t: dict) -> str:
    """Timestamp first. The classic mistake."""
    return f"{t['event_time']}#{t['trip_id']}"


def key_station_time(t: dict) -> str:
    """Station first, then time. The usual right answer."""
    return f"{t['start_station']}#{t['event_time']}"


def key_reversed_time(t: dict) -> str:
    """Station, then REVERSED timestamp - newest first within a station."""
    ts = int(datetime.fromisoformat(t["event_time"])
             .replace(tzinfo=timezone.utc).timestamp())
    return f"{t['start_station']}#{(2**31 - ts):010d}"


def key_salted(t: dict) -> str:
    """Hash prefix. Spreads perfectly and DESTROYS range scans."""
    h = hashlib.md5(t["trip_id"].encode()).hexdigest()[:2]
    return f"{h}#{t['start_station']}#{t['event_time']}"


DESIGNS = [
    ("timestamp first", key_sequential,
     "sequential - every write hits the same tablet"),
    ("station # time", key_station_time,
     "spreads by station, time-ordered within"),
    ("station # ~time", key_reversed_time,
     "same spread, newest first"),
    ("hash # station # time", key_salted,
     "perfect spread, NO range scan"),
]


def make_splits(keys: list[str], n: int) -> list[str]:
    """Split points that divide the sorted key space into n tablets.

    Real Bigtable splits a table at boundaries it chooses to balance
    STORAGE, so every tablet ends up holding roughly the same number of
    rows whatever the key design. Taking quantiles of the actual sorted
    keys models that faithfully.

    An earlier version used `ord(key[0]) % n`, which was wrong twice
    over: it only looked at the first byte, so every 'ST..' key landed
    on one tablet and station-first scored as badly as timestamp-first;
    and it measured STORAGE spread, which is not where hotspotting
    happens.
    """
    s = sorted(keys)
    step = max(1, len(s) // n)
    return [s[i * step] for i in range(1, n)]


def tablet_of(key: str, splits: list[str]) -> int:
    import bisect
    return bisect.bisect_right(splits, key)


# ============================================ 1-2. the model
def the_model() -> None:
    banner("1-2. What a Bigtable row is, and why sorting is everything")

    print("  A row is:  ROW KEY -> column families -> columns -> versioned cells")
    print("             every value is bytes, and every cell carries a timestamp\n")
    print("  There is exactly ONE index: the row key. No secondary indexes,")
    print("  no joins, no query planner. If an access pattern cannot be")
    print("  expressed as a prefix or a range of the row key, Bigtable")
    print("  cannot serve it without a full table scan.")

    print("\n  **Rows are stored SORTED by key, as bytes.** That single fact")
    print("  produces every design rule:")
    print("    - a prefix scan is cheap, because matching rows are adjacent")
    print("    - a range scan is cheap, for the same reason")
    print("    - keys that sort together are SERVED TOGETHER, by one tablet")
    print("      on one node - which is where hotspotting comes from")

    print("\n  Note it sorts LEXICOGRAPHICALLY, as bytes. So '10' sorts")
    print("  before '9', and an unpadded integer key does not range-scan")
    print("  the way you expect.")


# ============================================ 3. hotspotting
def hotspotting(trips: list[dict]) -> dict:
    banner("3. HOTSPOTTING - four key designs, measured")

    WINDOW = 100
    # Writes arrive in EVENT-TIME order, which is what a real ingest
    # looks like. Hotspotting is about which tablets a burst of
    # CONCURRENT writes lands on - not about where rows end up resting.
    arriving = sorted(trips, key=lambda t: t["event_time"])

    results = {}
    print(f"  {len(arriving):,} trips arriving in time order, across "
          f"{N_TABLETS} tablets.")
    print(f"  For each window of {WINDOW} CONSECUTIVE writes, how many "
          f"distinct")
    print(f"  tablets received them? {N_TABLETS} is perfect spread, 1 is a "
          f"single hot node.\n")
    print(f"  {'design':<24} {'tablets per burst':>18} {'worst':>7} "
          f"{'spread':>9}")
    print("  " + "-" * 66)

    for name, fn, _ in DESIGNS:
        keys = [fn(t) for t in arriving]
        splits = make_splits(keys, N_TABLETS)

        per_window = []
        for i in range(0, len(keys) - WINDOW + 1, WINDOW):
            per_window.append(
                len({tablet_of(k, splits) for k in keys[i:i + WINDOW]}))

        avg = sum(per_window) / len(per_window)
        worst = min(per_window)
        results[name] = {"avg_tablets": avg, "worst": worst,
                         "used": len(Counter(tablet_of(k, splits)
                                             for k in keys))}
        print(f"  {name:<24} {avg:>17.1f} {worst:>7} "
              f"{avg / N_TABLETS:>8.0%}")

    seq = results["timestamp first"]
    print(f"\n  **'timestamp first' touched {seq['avg_tablets']:.1f} tablet(s) "
          f"per burst of {WINDOW}.**")
    print("  Sequential keys are the classic Bigtable mistake: because rows")
    print("  sort by key, a monotonically increasing key means every write")
    print("  goes to the CURRENT END of the key space - one tablet, one")
    print("  node, while the rest of the cluster idles.")
    print("\n  It is also invisible in testing. A small dataset fits one")
    print("  tablet anyway, so the design only fails at the scale you")
    print("  bought Bigtable for.")

    print("\n  The same shape of problem as a Kafka hot partition")
    print("  (01_ingestion/02_kafka) and a Spark skewed key")
    print("  (04_managed_spark) - one key, one worker, no parallelism.")
    return results


# ============================================ 4. reads
def reads(client_table, trips: list[dict]) -> dict:
    banner("4. Point, prefix and range reads")

    from google.cloud.bigtable.row_set import RowSet

    station = trips[0]["start_station"]
    sample_key = key_station_time(trips[0])

    t0 = time.perf_counter()
    point = client_table.read_row(sample_key.encode())
    point_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    rs = RowSet()
    rs.add_row_range_from_keys(
        start_key=f"{station}#".encode(),
        end_key=f"{station}#\xff".encode())
    prefix_rows = list(client_table.read_rows(row_set=rs))
    prefix_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    all_rows = list(client_table.read_rows())
    scan_ms = (time.perf_counter() - t0) * 1000

    print(f"  {'read':<34} {'rows':>7} {'ms':>9}")
    print("  " + "-" * 54)
    print(f"  {'point read (exact key)':<34} {1 if point else 0:>7} "
          f"{point_ms:>9.1f}")
    print(f"  {f'prefix scan ({station}#)':<34} {len(prefix_rows):>7} "
          f"{prefix_ms:>9.1f}")
    print(f"  {'full table scan':<34} {len(all_rows):>7} {scan_ms:>9.1f}")

    print("\n  A point read and a prefix scan are both cheap because the")
    print("  rows are adjacent. **The full scan is the one to avoid** - and")
    print("  it is what every query that does not match the row key becomes.")
    print("\n  This is the real cost of getting the key wrong: there is no")
    print("  index to add later. The fix is to rewrite the table, or to")
    print("  maintain a second table keyed differently and write to both.")
    return {"point_ms": point_ms, "prefix_rows": len(prefix_rows),
            "prefix_ms": prefix_ms, "scan_rows": len(all_rows),
            "scan_ms": scan_ms}


# ============================================ 5. the rules
def the_rules(h: dict) -> None:
    banner("5. The design rules, and what they cost")

    salted = h["hash # station # time"]
    station = h["station # time"]

    print(f"  {'rule':<40} why")
    print("  " + "-" * 72)
    rows = [
        ("put the ACCESS PATTERN first", "prefix scans need it leftmost"),
        ("never start with a timestamp", f"measured: {h['timestamp first']['avg_tablets']:.1f} tablets per burst"),
        ("never start with a monotonic id", "same failure, same reason"),
        ("field-promote to spread", f"station first: {station['avg_tablets']:.1f} per burst"),
        ("reverse the timestamp for newest-first", "and still keep the prefix"),
        ("salt only as a last resort", "it destroys range scans"),
        ("keep keys short", "the key is stored in EVERY cell"),
    ]
    for a, b in rows:
        print(f"  {a:<40} {b}")

    print(f"\n  **Salting is not free, and the table above hides the cost.**")
    print(f"  'hash # station # time' reached "
          f"{salted['avg_tablets']:.1f} tablets per burst - the best")
    print("  distribution of the four. But the hash is now the leftmost")
    print("  component, so a scan for one station must read EVERY salt")
    print("  bucket. You traded a cheap prefix scan for a fan-out.")
    print("\n  Salt when the access pattern is genuinely point reads only.")
    print("  If you range-scan, promote a real field instead.")

    print("\n  >> The row key is not part of the schema. It IS the schema,")
    print("     and unlike a schema it cannot be altered later.")


def main() -> None:
    if not TRIPS.exists():
        raise SystemExit(f"  {TRIPS} not found - run 00_setup/make_data.py first.")

    print("=" * 72)
    print("  BIGTABLE ROW-KEY DESIGN".center(72))
    print("=" * 72)

    trips = load_trips()
    the_model()
    h = hotspotting(trips)

    try:
        with emulator():
            from google.cloud import bigtable
            from google.cloud.bigtable import column_family

            client = bigtable.Client(project=PROJECT, admin=True)
            instance = client.instance(INSTANCE)
            table = instance.table(TABLE)
            if not table.exists():
                table.create(column_families={
                    CF: column_family.MaxVersionsGCRule(1)})

            # Write with the RECOMMENDED design.
            rows = []
            for t in trips:
                r = table.direct_row(key_station_time(t).encode())
                r.set_cell(CF, b"duration", t["duration_min"].encode())
                r.set_cell(CF, b"bike", t["bike_type"].encode())
                rows.append(r)
            for i in range(0, len(rows), 1000):
                table.mutate_rows(rows[i:i + 1000])
            print(f"  wrote {len(rows):,} rows under 'station # time'\n")

            r = reads(table, trips)
            the_rules(h)

            banner("Summary - measured")
            print(f"  - 'timestamp first' reached only "
                  f"{h['timestamp first']['avg_tablets']:.1f} of {N_TABLETS} tablets "
                  f"per write burst - the classic hotspot")
            print(f"  - 'station # time'   reached "
                  f"{h['station # time']['avg_tablets']:.1f} of {N_TABLETS}")
            print(f"  - 'hash # ...'       reached "
                  f"{h['hash # station # time']['avg_tablets']:.1f} of {N_TABLETS}, "
                  f"and broke prefix scans")
            print(f"  - prefix scan returned {r['prefix_rows']:,} rows in "
                  f"{r['prefix_ms']:.0f} ms; full scan {r['scan_rows']:,} in "
                  f"{r['scan_ms']:.0f} ms")
            print("\n  One index, sorted, immutable. Design the key for the")
            print("  read you must serve, then check it spreads.")

    except RuntimeError as e:
        print(f"\n  EMULATOR UNAVAILABLE: {e}")
        print("\n  Section 3's hotspotting measurements above do not need it")
        print("  and are unaffected.")
        the_rules(h)


if __name__ == "__main__":
    main()
