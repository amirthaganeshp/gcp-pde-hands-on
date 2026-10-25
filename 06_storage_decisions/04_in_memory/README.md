# Memorystore — caching, TTL and eviction

> **Domain 3 (20%)** · Success Guide pp. 25–26 · Ultimate §3.1
> **Runtime:** ~3 s · **Needs:** `redis` client and `redis-server`

```bash
python 06_storage_decisions/04_in_memory/memorystore_caching.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

---

## 1. What it is

Managed **Redis** or **Memcached**. The API is unchanged, so a local `redis-server` behaves
identically — Google runs the failover, patching and replication.

It is on a *data engineering* exam for one reason: **a cache is volatile**, and treating it as a
store is data loss waiting to happen.

## 2. Components

| component | what it is |
|---|---|
| **Instance** | Basic (no replica) or Standard (replica + automatic failover). |
| **`maxmemory`** | The ceiling. Reached, it triggers eviction. |
| **Eviction policy** | *What* gets discarded — or whether writes fail instead. |
| **TTL** | Per-key expiry. `-1` means never. |
| **Read replicas** | Scale reads on the Standard tier. |

## 3. Engines and tiers

| | **Redis** | **Memcached** |
|---|---|---|
| data types | strings, hashes, lists, sets, **sorted sets**, streams | strings only |
| persistence | optional snapshots (Standard tier) | **none** |
| replication / HA | **yes** (Standard tier) | no — scale by adding nodes |
| best at | leaderboards, session state, rate limiting, pub/sub | a **large, simple, horizontally-scaled** key-value cache |

**Redis is the exam default.** Memcached appears when the scenario stresses a very large, simple
cache scaled across many nodes with no need for data structures or failover.

> **Sorted sets are why "real-time leaderboard" always means Redis.** Rank-ordered reads and
> in-place score updates are a native operation, not something you rebuild.

| tier | gives you |
|---|---|
| **Basic** | a single node. **A restart loses everything** — pure cache. |
| **Standard** | a replica in another zone with **automatic failover**, and read replicas. |

**Neither tier makes it a database.** Standard reduces how often you lose the cache; it does not
make the data durable.

### The access patterns

| pattern | how it works | the risk |
|---|---|---|
| **Cache-aside** (lazy) | app reads cache, misses, reads DB, writes cache | stale until TTL; a **cache stampede** when a hot key expires |
| **Write-through** | every write goes to cache **and** DB | consistent, slower writes, caches data nobody reads |
| **Write-back** | write to cache, flush to DB later | fastest, and **loses data on failure** — rarely right here |

## 4. Fundamental operations

| measured | result |
|---|---|
| 36 lookups, 8 keys, one hot | **28 hits / 8 misses**, 78% hit rate |
| cache-aside vs always-slow | **4.0× faster** |
| key with no TTL | `ttl = -1` — never expires |
| 5,000 keys into a 2 MB cache | **4,517 evicted**, 495 survive |

## 5. Nuances — the part worth reading

**A cache is not a store, and this is measurable.** Writing 5,000 keys into a 2 MB instance:
**4,517 were written successfully and then silently discarded.** Every `SET` returned OK. No
error, no warning — discarding is the cache's job.

> Anything you cannot recompute from the source must not live only here.

**The eviction policy decides what goes — and whether anything goes at all:**

| policy | behaviour |
|---|---|
| `allkeys-lru` | evict least-recently-used — a true cache |
| `volatile-lru` | evict **only keys that have a TTL** |
| `noeviction` | **refuse writes** rather than evict |

> **`volatile-*` with no TTLs set behaves like `noeviction`** — nothing is eligible, so writes
> start failing instead. That combination is a common and very confusing outage.

**A TTL is a statement about staleness, not memory management.** A cached value is a copy, and
copies go stale; the TTL is how wrong you are willing to be. Keys with `ttl = -1` accumulate until
the eviction policy decides their fate for you.

**The hit rate comes from the access pattern, not from the cache.** 78% here because one key was
hot. A uniform random workload over a large keyspace caches badly however much memory you buy —
buying more memory is the wrong first response to a low hit rate.

**Cache-aside is the default pattern** — look in the cache, on a miss fetch and populate. The
application owns the logic, so the cache never needs to know about the source. Write-through is
fresher and gives you two things to keep in step plus a failure mode between them.

## 6. When to use it — and when not

| situation | reach for |
|---|---|
| repeated reads of the same small values | **Memorystore** |
| session state, rate limiting, leaderboards | **Memorystore (Redis)** |
| a slow query that scans | **fix the query** — partition, cluster |
| a slow dashboard | **pre-aggregate** or BI Engine |
| durable state | a database — **a cache evicts** |
| each key read once | nothing — a cache is pure overhead |

**A cache hides a slow query; it does not make it fast.** If the query scans a partition it should
have pruned, the cache only means you pay for that scan less often.

**Redis vs Memcached:** Redis unless the question stresses a simple, very large, multi-threaded
string cache. Redis has data structures, persistence, replication and pub/sub; Memcached has
strings and more cores.

## 6. What was actually run

| | |
|---|---|
| `memorystore_caching.py` | ✅ **fully executed**, exit 0 |
| Redis | local `redis-server`, started and stopped by the script, `maxmemory 2mb` |
| Cloud resources | **none** |

The instance is deliberately tiny so **eviction can be observed rather than described**. The
managed aspects — tiers, replicas, failover, maintenance windows — are 📝 write-only.
