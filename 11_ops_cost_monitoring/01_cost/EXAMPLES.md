# Cost — what the illustration shows

The README explains the *levers*. This file explains the *script*: what it computes, and why two
of these numbers are decisions rather than opinions.

---

## `bigquery_economics.py`

**Setup:** pure Python over published pricing. No project, no billing API. **A computation, not a
simulation.**

| § | it does | measured |
|---|---|---|
| 1 | prices a always-on reservation against on-demand | 100 Enterprise slots = **$4,380/month** |
| 2 | solves for the break-even scan volume | **702 TiB/month** (**421 TiB** with a 3-year commitment) |
| 3 | compares logical vs physical storage billing | physical wins above **2.0×** compression |
| 4 | applies the long-term storage discount | **50% off** after 90 days untouched |

## §2 — 702 TiB is a very large number

```
100 Enterprise slots, always on  =  $4,380 / month
crossover with on-demand         =  702 TiB scanned / month
with a 3-year commitment         =  421 TiB
```

**Most teams asking "should we buy slots?" are nowhere near it on cost grounds.**

> The real reasons to buy capacity are **predictability and protection from throttling**, not the
> average bill. A question that says "predictable spend" or "BI queries must never be throttled"
> is asking about those — not about this crossover.

**On-demand bills work done. Capacity bills time reserved.** A reservation costs the same
saturated or idle, which is why comparing them per-query is the wrong frame, and why **sizing a
reservation for the peak** is how people end up paying for idle slots all night. Most real estates
want both: a baseline reservation for steady load, with autoscale or on-demand absorbing peaks.

## §4 — the long-term discount triggers on the wrong intuition

**50% off after 90 days *untouched*. Reading does not reset the clock; *writing* does.**

> So a pipeline that rewrites a whole table daily keeps **every byte at active pricing forever**.
> The same data as date partitions — where only today's partition changes — lets everything older
> age into the discount automatically.

**Partitioning is therefore a storage-cost decision as well as a query-cost one**, which is not
obvious from either price list.

## The four controls that actually prevent spend

| | |
|---|---|
| `require_partition_filter` | makes an unpruned query an **error** |
| `maximum_bytes_billed` | the query **aborts before charging** |
| custom quotas | a per-user or per-project daily ceiling |
| a reservation ceiling | caps compute by construction |

> **A budget alert is a notification, not a cap.** By the time it fires the money is already spent.
> It is routinely mistaken for a control, and the distinction is worth a mark.

Two more from the README that surprise people: the query cache is **free for 24 h** on an identical
query over unchanged tables, and `DELETE FROM t WHERE true` **scans and bills the whole table**
while `TRUNCATE TABLE t` is **free and instant**.

## What this cannot show

Not demonstrated: actual slot consumption, reservation autoscaling behaviour, Editions feature
differences, CUD/SUD application, or billing export. Those need a real account with real usage.

**What transfers is the arithmetic and the direction of every lever** — the crossover formula holds
wherever the prices land, and the prices are printed so a stale number is visible.
