"""Memorystore: caching patterns, TTL, and what eviction really means.

Memorystore is managed Redis (or Memcached). The API is Redis, so a
local redis-server behaves identically - only the operating changes.

The reason it is on a DATA ENGINEERING exam is not "caching is fast".
It is that a cache is VOLATILE, and treating it as a store is a data
loss waiting to happen.

  1. Cache-aside - the pattern, measured
  2. TTL - and why a cache without one is a bug
  3. EVICTION - what happens when memory runs out
  4. Redis or Memcached?
  5. When a cache is the wrong answer

EXECUTED IN FULL against a local redis-server this file starts and
stops itself.

Run:
    python 06_storage_decisions/04_in_memory/memorystore_caching.py

Guide reference: Success Guide pp. 25-26; Ultimate Edition section 3.1.
"""

from __future__ import annotations

import contextlib
import csv
import shutil
import socket
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRIPS = REPO / "data" / "trips.csv"
PORT = 6399                      # not 6379, to avoid a real local redis

SLOW_QUERY_MS = 25               # stands in for a BigQuery round trip


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


@contextlib.contextmanager
def redis_server(port: int = PORT):
    if shutil.which("redis-server") is None:
        raise RuntimeError(
            "redis-server not found. Install it:\n"
            "    sudo apt-get install -y redis-server")

    with contextlib.closing(socket.socket()) as s:
        s.settimeout(1.0)
        if s.connect_ex(("127.0.0.1", port)) == 0:
            print(f"  Redis already on :{port} - reusing.\n")
            yield
            return

    print(f"  Starting redis-server on :{port} ...")
    proc = subprocess.Popen(
        ["redis-server", "--port", str(port), "--save", "",
         "--appendonly", "no",
         # A deliberately tiny cache, so eviction can be observed in
         # section 3 rather than described.
         "--maxmemory", "2mb", "--maxmemory-policy", "allkeys-lru"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for _ in range(40):
        with contextlib.closing(socket.socket()) as s:
            s.settimeout(1.0)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.25)
    else:
        proc.terminate()
        raise RuntimeError("redis did not start within 10 s")

    print("  Redis up.\n")
    try:
        yield
    finally:
        proc.terminate()
        with contextlib.suppress(Exception):
            proc.wait(timeout=10)
        print("\n  Redis stopped.")


def load_stations() -> dict[str, dict]:
    agg: dict[str, dict] = {}
    with TRIPS.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s = agg.setdefault(r["start_station"],
                               {"trips": 0, "total_min": 0.0})
            s["trips"] += 1
            s["total_min"] += float(r["duration_min"])
    return agg


def slow_lookup(station: str, source: dict) -> dict:
    """Stand-in for the expensive query a cache exists to avoid."""
    time.sleep(SLOW_QUERY_MS / 1000)
    return source[station]


# ============================================ 1. cache-aside
def cache_aside(r, source: dict) -> dict:
    banner("1. Cache-aside - the pattern, measured")

    stations = list(source)
    hits = misses = 0

    def get(station: str) -> dict:
        nonlocal hits, misses
        cached = r.get(f"station:{station}")
        if cached is not None:
            hits += 1
            return {"cached": True}
        misses += 1
        value = slow_lookup(station, source)          # the expensive path
        r.setex(f"station:{station}", 300, str(value))
        return value

    # A realistic access pattern: a few stations dominate.
    pattern = stations * 2 + [stations[0]] * 20

    t0 = time.perf_counter()
    for s in pattern:
        get(s)
    cached_s = time.perf_counter() - t0

    uncached_s = len(pattern) * SLOW_QUERY_MS / 1000

    print(f"  {len(pattern)} lookups over {len(stations)} stations, "
          f"one of them hot\n")
    print(f"  {'':<22} {'seconds':>9}")
    print("  " + "-" * 34)
    print(f"  {'every lookup slow':<22} {uncached_s:>9.2f}")
    print(f"  {'with cache-aside':<22} {cached_s:>9.2f}")
    print(f"\n  hits {hits}, misses {misses}  "
          f"({hits / (hits + misses):.0%} hit rate)")
    print(f"  speedup: {uncached_s / cached_s:.1f}x")

    print("\n  **Cache-aside: look in the cache; on a miss, fetch and")
    print("  populate.** The application owns the logic, which is why it is")
    print("  the default - the cache never needs to know about the source.")

    print("\n  The hit rate is the whole game, and it comes from the access")
    print("  pattern rather than from the cache. A uniform random workload")
    print("  over a large keyspace caches badly no matter how much memory")
    print("  you buy.")
    return {"hits": hits, "misses": misses, "cached_s": cached_s,
            "uncached_s": uncached_s}


# ============================================ 2. TTL
def ttl_demo(r) -> dict:
    banner("2. TTL - a cache without one is a bug")

    r.setex("short", 1, "value")
    before = r.get("short")
    ttl_before = r.ttl("short")
    time.sleep(1.2)
    after = r.get("short")

    r.set("forever", "value")             # no TTL
    ttl_forever = r.ttl("forever")

    print(f"  {'key':<12} {'TTL set':>9} {'after 1.2 s':>14}")
    print("  " + "-" * 40)
    print(f"  {'short':<12} {str(ttl_before) + ' s':>9} "
          f"{'gone' if after is None else 'still there':>14}")
    print(f"  {'forever':<12} {str(ttl_forever):>9} "
          f"{'still there':>14}   <- ttl -1 means NO expiry")

    print("\n  **A cached value is a copy, and copies go stale.** The TTL is")
    print("  your statement about how wrong you are willing to be - not a")
    print("  memory-management setting.")

    print("\n  `ttl` of -1 means the key never expires. Those keys accumulate")
    print("  until something evicts them, and what gets evicted is decided")
    print("  by the policy, not by you - see section 3.")

    print("\n  Two invalidation strategies, and the trade between them:")
    print("    TTL only        simple, always eventually consistent, and")
    print("                    stale for up to the TTL")
    print("    write-through   update the cache when you update the source;")
    print("                    fresher, and now you have two things to keep")
    print("                    in step and a failure mode between them")
    return {"expired": after is None, "no_ttl": ttl_forever}


# ============================================ 3. eviction
def eviction(r) -> dict:
    banner("3. EVICTION - what happens when memory runs out")

    r.flushdb()
    payload = "x" * 2000

    stored = 0
    for i in range(5000):
        try:
            r.set(f"fill:{i}", payload)
            stored += 1
        except Exception:
            break

    remaining = r.dbsize()
    info = r.info("stats")
    evicted = info.get("evicted_keys", 0)
    mem = r.info("memory")

    print(f"  maxmemory        : {mem['maxmemory'] / 1024 / 1024:.1f} MB")
    print(f"  policy           : {r.config_get('maxmemory-policy')['maxmemory-policy']}")
    print(f"  keys written     : {stored:,}")
    print(f"  keys still there : {remaining:,}")
    print(f"  keys EVICTED     : {evicted:,}")

    print(f"\n  **{evicted:,} keys were written successfully and then thrown")
    print("  away.** No error, no warning - every `SET` returned OK.")

    print("\n  That is the fact that matters for a data engineer: **a cache")
    print("  is not a store.** It will silently discard data under pressure,")
    print("  because discarding is its job. Anything you cannot recompute")
    print("  from the source must not live only here.")

    print("\n  The policy decides WHAT goes:")
    print("    allkeys-lru     evict the least recently used - a true cache")
    print("    volatile-lru    evict only keys that have a TTL")
    print("    noeviction      REFUSE WRITES instead of evicting - the right")
    print("                    choice when Redis is a queue or a store, and")
    print("                    the wrong one for a cache")

    print("\n  `volatile-*` with no TTLs set behaves like `noeviction`:")
    print("  nothing is eligible, so writes start failing. That combination")
    print("  is a common and very confusing outage.")
    return {"stored": stored, "remaining": remaining, "evicted": evicted}


# ============================================ 4-5. the decisions
def decisions() -> None:
    banner("4. Redis or Memcached?")

    rows = [
        ("data structures", "lists, sets, sorted sets, streams", "strings only"),
        ("persistence", "RDB/AOF snapshots available", "none"),
        ("replication / HA", "yes", "no"),
        ("pub/sub", "yes", "no"),
        ("multi-threaded", "mostly single", "yes, scales on cores"),
        ("use when", "you need any of the above", "a pure LRU string cache"),
    ]
    print(f"  {'':<18} {'Redis':<36} Memcached")
    print("  " + "-" * 74)
    for a, b, c in rows:
        print(f"  {a:<18} {b:<36} {c}")

    print("\n  **Redis is the default answer** unless the question stresses")
    print("  a simple, very large, multi-threaded string cache. Memorystore")
    print("  offers both; Redis is what most questions describe.")

    banner("5. When a cache is the WRONG answer")

    rows2 = [
        ("the query is slow because it scans", "fix the query - partition, cluster"),
        ("the dashboard is slow", "pre-aggregate or BI Engine"),
        ("you need durable state", "a database - a cache evicts"),
        ("every key is read once", "a cache is pure overhead"),
        ("the data must never be stale", "read the source"),
    ]
    print(f"  {'situation':<42} instead")
    print("  " + "-" * 72)
    for a, b in rows2:
        print(f"  {a:<42} {b}")

    print("\n  A cache hides a slow query; it does not make it fast. If the")
    print("  underlying query scans a partition it should have pruned, the")
    print("  cache just means you pay for that scan slightly less often.")


def main() -> None:
    if not TRIPS.exists():
        raise SystemExit(f"  {TRIPS} not found - run 00_setup/make_data.py first.")

    print("=" * 72)
    print("  MEMORYSTORE - caching, TTL and eviction".center(72))
    print("=" * 72)

    try:
        with redis_server():
            import redis
            r = redis.Redis(host="localhost", port=PORT, decode_responses=True)
            r.flushdb()

            source = load_stations()
            c = cache_aside(r, source)
            t = ttl_demo(r)
            e = eviction(r)
            decisions()

            banner("Summary - measured against a local Redis")
            print(f"  - cache-aside: {c['hits']} hits / {c['misses']} misses, "
                  f"{c['uncached_s'] / c['cached_s']:.1f}x faster")
            print(f"  - a key with no TTL never expires "
                  f"(ttl = {t['no_ttl']}) and waits to be evicted")
            print(f"  - under memory pressure, {e['evicted']:,} keys were "
                  f"written OK and then silently discarded")
            print("\n  A cache is volatile by design. Speed is why you want")
            print("  one; eviction is why it can never be the only copy.")

    except RuntimeError as exc:
        print(f"\n  SKIPPED: {exc}")


if __name__ == "__main__":
    main()
