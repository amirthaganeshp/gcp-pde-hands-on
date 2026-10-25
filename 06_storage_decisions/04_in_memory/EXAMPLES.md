# Memorystore — what the illustration shows

The README explains the *service*. This file explains the *script*: what it sets up, what it
measures, and the one result that matters more than the rest.

---

## `memorystore_caching.py`

**Setup:** a **real Redis server**, started and stopped by the script, deliberately capped at
**2 MB** with an eviction policy set. The API is identical to Memorystore's — Memorystore *is*
Redis, managed.

| § | it does | measured | the exam idea |
|---|---|---|---|
| 1 | cache-aside reads: miss → source → populate | **78%** hit rate | the hit rate comes from the *workload* |
| 2 | sets keys with and without TTL | `ttl = -1` never expires | a TTL is a staleness statement |
| 3 | **writes 5,000 keys into a 2 MB instance** | **4,517 silently evicted** | **a cache is not a store** |
| 4 | compares eviction policies | `volatile-*` with no TTLs ≈ `noeviction` | the policy decides *whether* anything goes |

## §3 — the result to take away

```
5,000 keys written   -> every SET returned OK
4,517 keys gone      -> no error, no warning, no exception
```

**Every single write succeeded.** Redis accepted them, then discarded 90% of them to stay under
`maxmemory`. Discarding is not a failure here — it is the cache doing its job, correctly, and
saying nothing.

> **Anything you cannot recompute from the source must not live only here.** That is the entire
> data-engineering content of this service, and it is why a "cache" holding the only copy of
> something is a design error rather than a tuning problem.

This belongs to the same family as late data dropped at `allowed_lateness = 0` and a naive CDC
merge returning 464 rows against a truth of 461 — see
[`99_reference/FINDINGS.md`](../../99_reference/FINDINGS.md) §2, *failures that raise nothing*.

## §4 — the policy combination that causes outages

| policy | behaviour |
|---|---|
| `allkeys-lru` | evict least-recently-used — a true cache |
| `volatile-lru` | evict **only keys that have a TTL** |
| `noeviction` | **refuse writes** rather than evict |

**`volatile-lru` with no TTLs set behaves exactly like `noeviction`.** Nothing is eligible for
eviction, so instead of quietly losing data the instance starts **rejecting writes**. Same
configuration, opposite failure, and the switch between them is whether anyone remembered to set
TTLs.

## §1 — why the hit rate is not a cache property

78% here **because one key was hot**. A uniform random workload over a large keyspace caches badly
no matter how much memory you buy.

> **Buying more memory is the wrong first response to a low hit rate.** The right question is
> whether the access pattern has any locality to exploit.

## What running a local Redis cannot show

Not demonstrated, and not simulated: Memorystore's Basic vs Standard tiers, replica failover, read
replicas, maintenance windows, VPC integration, or persistence snapshots. Those are properties of
the managed service.

**What transfers completely** is everything above — eviction, TTL semantics and hit-rate behaviour
are Redis, and Memorystore is Redis.
