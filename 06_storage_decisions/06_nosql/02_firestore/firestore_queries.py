"""Firestore: documents, indexes, and the limits that decide the design.

Firestore is the other NoSQL option, and it is nothing like Bigtable.
Bigtable has one sorted index and no queries; Firestore indexes EVERY
field automatically and has a real query language - but constrains what
those queries may do, and charges per document read.

  1. Documents and collections - the model
  2. Queries, and the indexes that make them possible
  3. The COMPOSITE INDEX requirement - the thing that fails in prod
  4. What Firestore will not do, and why
  5. Firestore or Bigtable?

EXECUTED IN FULL against the local Firestore emulator, which this file
starts and stops itself.

Run:
    python 06_storage_decisions/06_nosql/02_firestore/firestore_queries.py

Guide reference: Success Guide pp. 30-31; Ultimate Edition section 3.3.
"""

from __future__ import annotations

import contextlib
import csv
import os
import signal
import shutil
import socket
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TRIPS = REPO / "data" / "trips.csv"

PROJECT = "local-demo"
PORT = 8087
N_DOCS = 400


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


def find_gcloud() -> str:
    if os.path.exists("/usr/bin/gcloud"):
        return "/usr/bin/gcloud"
    found = shutil.which("gcloud")
    if found and found.startswith("/mnt/"):
        raise RuntimeError(
            f"only a Windows gcloud is on PATH ({found}); install the Linux "
            "one:\n    sudo apt-get install -y google-cloud-cli "
            "google-cloud-cli-firestore-emulator")
    if not found:
        raise RuntimeError(
            "gcloud not found:\n    sudo apt-get install -y "
            "google-cloud-cli google-cloud-cli-firestore-emulator")
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
def emulator(port: int = PORT):
    gcloud = find_gcloud()
    with contextlib.closing(socket.socket()) as s:
        s.settimeout(1.0)
        if s.connect_ex(("127.0.0.1", port)) == 0:
            print(f"  Emulator already on :{port} - reusing.\n")
            os.environ["FIRESTORE_EMULATOR_HOST"] = f"localhost:{port}"
            yield
            return

    print(f"  Starting Firestore emulator on :{port} ...")
    proc = subprocess.Popen(
        [gcloud, "beta", "emulators", "firestore", "start",
         f"--host-port=localhost:{port}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)   # own process group - see _stop_emulator
    os.environ["FIRESTORE_EMULATOR_HOST"] = f"localhost:{port}"

    for _ in range(80):
        with contextlib.closing(socket.socket()) as s:
            s.settimeout(1.0)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError("firestore emulator did not start within 40 s")

    time.sleep(1)
    print("  Emulator up.\n")
    try:
        yield
    finally:
        _stop_emulator(proc, port)
        print("\n  Emulator stopped.")


def load_trips(limit: int = N_DOCS) -> list[dict]:
    out = []
    with TRIPS.open(encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f)):
            if i >= limit:
                break
            out.append(r)
    return out


# ============================================ 1. the model
def the_model() -> None:
    banner("1. Documents and collections")

    print("  collection -> document -> fields")
    print("                         -> SUBcollection -> document -> ...\n")
    print("  A document is a JSON-like object with typed fields, up to")
    print("  1 MiB. A collection is just a namespace - it has no schema and")
    print("  documents in it need not resemble each other.")

    print("\n  **Firestore indexes every field automatically**, which is the")
    print("  opposite of Bigtable's single sorted key. That is why it can")
    print("  answer real queries - and why writes cost more, since every")
    print("  index has to be updated.")

    print("\n  Subcollections are how you model hierarchy without joins.")
    print("  They are NOT loaded with the parent - querying a document does")
    print("  not fetch its subcollections, which is exactly what makes deep")
    print("  nesting cheap to read.")


# ============================================ 2-3. queries and indexes
def queries(db, trips: list[dict]) -> dict:
    banner("2-3. Queries, and the composite-index requirement")

    from google.cloud.firestore_v1.base_query import FieldFilter

    col = db.collection("trips")
    batch = db.batch()
    for i, t in enumerate(trips):
        batch.set(col.document(t["trip_id"]), {
            "station": t["start_station"],
            "bike_type": t["bike_type"],
            "duration_min": float(t["duration_min"]),
            "member": t["member"] == "True",
        })
        if (i + 1) % 400 == 0:
            batch.commit()
            batch = db.batch()
    batch.commit()
    print(f"  wrote {len(trips)} documents\n")

    results = {}

    # single field - served by an automatic single-field index
    t0 = time.perf_counter()
    n1 = len(list(col.where(filter=FieldFilter("station", "==", "ST01"))
                  .stream()))
    results["equality"] = (n1, (time.perf_counter() - t0) * 1000)

    # equality + range on ANOTHER field - needs a COMPOSITE index
    t0 = time.perf_counter()
    n2 = len(list(col.where(filter=FieldFilter("station", "==", "ST01"))
                  .where(filter=FieldFilter("duration_min", ">", 15))
                  .stream()))
    results["composite"] = (n2, (time.perf_counter() - t0) * 1000)

    # ordering by a different field than the range - the classic failure
    try:
        t0 = time.perf_counter()
        n3 = len(list(col.where(filter=FieldFilter("duration_min", ">", 15))
                      .order_by("station").limit(10).stream()))
        results["order_mismatch"] = (n3, (time.perf_counter() - t0) * 1000,
                                     None)
    except Exception as e:
        results["order_mismatch"] = (0, 0, type(e).__name__)

    print(f"  {'query':<42} {'docs':>6} {'ms':>8}")
    print("  " + "-" * 60)
    print(f"  {'station == ST01':<42} {results['equality'][0]:>6} "
          f"{results['equality'][1]:>8.1f}")
    print(f"  {'station == ST01 AND duration > 15':<42} "
          f"{results['composite'][0]:>6} {results['composite'][1]:>8.1f}")
    om = results["order_mismatch"]
    print(f"  {'duration > 15 ORDER BY station':<42} "
          f"{om[0]:>6} {'ERR' if om[2] else format(om[1], '.1f'):>8}")

    print("\n  ** ALL THREE QUERIES SUCCEEDED HERE. AT LEAST ONE WOULD NOT")
    print("  IN PRODUCTION - and that gap is the finding. **")

    print("\n  Query 2 needs a COMPOSITE INDEX: an equality on one field")
    print("  plus a range on another cannot be served by the automatic")
    print("  single-field indexes. **The emulator creates composite indexes")
    print("  on demand; production does not.** There it fails with")
    print("  FAILED_PRECONDITION and a link to go and create the index.")

    print("\n  Query 3 breaks the ordering rule - if you range-filter on a")
    print("  field, your first order_by must be THAT field, because")
    print("  Firestore cannot sort by one field while scanning an index")
    print("  ordered by another. The emulator permitted it anyway.")

    print("\n  So 'it worked locally' carries less weight for Firestore than")
    print("  for almost anything else here. The practical consequence:")
    print("  **keep firestore.indexes.json in source control and deploy it**,")
    print("  rather than discovering the required indexes from production")
    print("  errors one at a time.")
    return results


# ============================================ 4. the limits
def the_limits() -> None:
    banner("4. What Firestore will not do")

    rows = [
        ("1 MiB", "max document size"),
        ("1 write/sec", "sustained, per DOCUMENT - the hot-document limit"),
        ("500", "documents per batched write / transaction"),
        ("no aggregation", "beyond count/sum/avg - no GROUP BY"),
        ("no joins", "denormalise, or read twice"),
        ("no OR across fields", "until recently - and it is index-expensive"),
        ("billed per document READ", "not per byte, not per query"),
    ]
    print(f"  {'limit':<26} what it means")
    print("  " + "-" * 66)
    for a, b in rows:
        print(f"  {a:<26} {b}")

    print("\n  **The per-document write limit is the design constraint.**")
    print("  One counter document updated on every event caps at roughly")
    print("  one write a second, whatever else you do - the Firestore")
    print("  version of a hot key. The fix is DISTRIBUTED COUNTERS: shard")
    print("  the counter across N documents and sum on read.")

    print("\n  **Billing per document read decides schema design.** A query")
    print("  returning 10,000 documents costs 10,000 reads even if you")
    print("  needed one field from each. Denormalising a summary into the")
    print("  parent document to avoid reading children is not a hack here -")
    print("  it is the cost model working as intended.")

    print("\n  Native mode vs Datastore mode: **choose Native for anything")
    print("  new.** Datastore mode exists for App Engine compatibility, and")
    print("  loses realtime listeners and offline sync.")


# ============================================ 5. the choice
def firestore_or_bigtable() -> None:
    banner("5. Firestore or Bigtable?")

    rows = [
        ("index", "every field, automatic", "the row key, and only that"),
        ("queries", "filters, ordering, limits", "prefix and range scans"),
        ("scale ceiling", "large", "petabytes, millions of ops/sec"),
        ("latency", "tens of ms", "single-digit ms"),
        ("billed on", "document reads/writes", "nodes and storage"),
        ("realtime sync", "yes - listeners, offline", "no"),
        ("best at", "app state, user data, documents", "time series, events, telemetry"),
    ]
    print(f"  {'':<16} {'Firestore':<32} Bigtable")
    print("  " + "-" * 74)
    for a, b, c in rows:
        print(f"  {a:<16} {b:<32} {c}")

    print("\n  **Firestore is an application database; Bigtable is an")
    print("  analytical-scale key-value store.** The giveaway in a question")
    print("  is whether an APP is reading it (Firestore - mobile, web,")
    print("  offline, realtime) or a PIPELINE is (Bigtable - ingest rate,")
    print("  time series, scans).")

    print("\n  Neither is an analytics store. 'Report across all of it' is")
    print("  BigQuery in both cases - and Firestore has a managed export to")
    print("  BigQuery for exactly that.")


def main() -> None:
    if not TRIPS.exists():
        raise SystemExit(f"  {TRIPS} not found - run 00_setup/make_data.py first.")

    print("=" * 72)
    print("  FIRESTORE - documents, indexes and limits".center(72))
    print("=" * 72)

    the_model()

    try:
        with emulator():
            from google.cloud import firestore
            db = firestore.Client(project=PROJECT)

            trips = load_trips()
            q = queries(db, trips)
            the_limits()
            firestore_or_bigtable()

            banner("Summary - measured against the emulator")
            print(f"  - equality query      : {q['equality'][0]} docs in "
                  f"{q['equality'][1]:.0f} ms")
            print(f"  - equality + range    : {q['composite'][0]} docs in "
                  f"{q['composite'][1]:.0f} ms (needs a COMPOSITE index)")
            print(f"  - order-by mismatch   : {q['order_mismatch'][0]} docs "
                  f"- ALLOWED here, rejected in production")
            print("  - the emulator is permissive: it builds composite")
            print("    indexes on demand and let all three queries through")
            print("\n  Every field indexed, real queries, and a hard limit of")
            print("  about one write per second per document. Design around")
            print("  the document, not around the query.")

    except RuntimeError as e:
        print(f"\n  EMULATOR UNAVAILABLE: {e}")
        the_limits()
        firestore_or_bigtable()


if __name__ == "__main__":
    main()
