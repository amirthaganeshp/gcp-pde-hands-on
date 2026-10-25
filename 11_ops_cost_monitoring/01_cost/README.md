# Cost optimisation

> **Domain 5 — Maintaining and Automating Workloads (18%)** · Success Guide pp. 36–37 · Ultimate §5.1, §5.3
> **Runtime:** <1 s · **Needs:** nothing — pure Python

```bash
python 11_ops_cost_monitoring/01_cost/bigquery_economics.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

---

## 1. What it is

Cost on GCP is mostly **arithmetic with a few thresholds**, not judgement. This folder computes
the thresholds rather than asserting them.

**Measured:**

| decision | crossover |
|---|---|
| on-demand vs capacity pricing | **702 TiB** scanned/month (**421 TiB** with a 3-year commitment) |
| logical vs physical storage billing | **2.0×** compression |

## 2. The BigQuery playbook

| lever | effect | note |
|---|---|---|
| **Avoid `SELECT *`** | bills only the columns referenced | measured **11.8×** in [`../../03_bigquery/`](../../03_bigquery/) |
| **Partition + cluster** | narrows the blocks scanned | **13.3×** and **6.2×** measured |
| **Query cache** | identical query on unchanged tables is **free for 24 h** | free, and frequently forgotten |
| **`--maximum_bytes_billed`** | the query **aborts before charging** if the estimate exceeds it | **the only hard per-query stop** |
| **`--dry_run`** | free estimate of bytes | run it on anything unfamiliar |
| **Table / partition expiration** | temp and staging data deletes itself | the cheapest storage is deleted storage |
| **`TRUNCATE` not `DELETE`** | `DELETE FROM t WHERE true` **scans everything and bills for it**; `TRUNCATE` is **free and instant** | a genuinely surprising one |

### Pricing models

| | on-demand | capacity (Editions) |
|---|---|---|
| bills | **bytes scanned** (~$5/TB, first 1 TiB/month free) | **slot-hours** |
| tiers | — | Standard · Enterprise · Enterprise Plus |
| commitments | — | 1-year / 3-year, steeply discounted |
| fits | bursty, unpredictable | predictable enterprise load |

**Reservations** assign slot pools to projects or folders — e.g. 500 slots dedicated to production
dashboards so BI queries are never throttled, dev sandboxes routed to a shared 100.

### Storage billing

- **Long-term storage**: 50% off after **90 days untouched**. **Reading does not reset the clock;
  *writing* does.**
- **Logical vs physical**: physical bills compressed bytes and is cheaper **above 2.0× compression**
  — measured, not assumed.

## 3. Infrastructure levers

| lever | saving |
|---|---|
| **Spot / Preemptible VMs** | up to **80%** — Dataproc secondary workers, GKE batch pods |
| **Sustained Use Discounts** | automatic on Compute Engine run for much of the month |
| **Committed Use Discounts** | 1 or 3 years of CPU/RAM/**BigQuery slots** |
| **GCS lifecycle policies** | auto-transition cold data to colder classes |
| **Scheduling non-prod VMs** | Scheduler + Functions to stop them nights and weekends |
| **Dataflow FlexRS** | preemptible mix for non-urgent batch, queued up to 6 h |

## 4. Nuances — the part worth reading

**702 TiB/month is a very large number.** Most teams asking "should we buy slots?" are nowhere near
it on *cost* grounds. The real reasons to buy capacity are **predictability and throttling
protection**, not the average bill — and a question that says "predictable spend" is asking about
that, not the crossover.

**Reservations bill time reserved, not work done.** An idle reservation costs exactly the same as a
busy one. This is the opposite of on-demand's failure mode, and it is how capacity pricing becomes
*more* expensive than the thing it replaced.

**`DELETE FROM t WHERE true` is billable and slow; `TRUNCATE TABLE t` is free and instant.** Both
empty the table.

**The cache is free but fragile** — any change to the underlying table invalidates it, and
non-deterministic functions (`CURRENT_TIMESTAMP()`) prevent it entirely.

**Billing export to BigQuery is the actual answer to "how do we track this?"** — costs become a
table you can query and dashboard, rather than a console page.

## 5. What was actually run

| | |
|---|---|
| `bigquery_economics.py` | ✅ **fully executed** — crossovers computed, not quoted |
| Cloud resources | **none** |

📝 **Documented, not demonstrated:** reservations, Editions, CUD/SUD, billing export. These are
account-level billing constructs with nothing to simulate.
