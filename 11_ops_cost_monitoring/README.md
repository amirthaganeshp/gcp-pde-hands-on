# Operations, cost and monitoring

> **Domain 5 — Maintaining and Automating Data Workloads (18%)** · Success Guide pp. 36–37, 48–50,
> 115–117 · Ultimate §5.1, §5.3, §5.4

| service | covers | state |
|---|---|---|
| [`01_cost/`](01_cost/) | on-demand vs capacity, Editions, storage billing, cost controls | ✅ built |
| [`02_monitoring/`](02_monitoring/) | metric types, **alerting conditions**, duration windows | ✅ built |
| [`03_logging/`](03_logging/) | audit log types, sinks, exclusions, log-based metrics | 📝 documented |

---

## 1. What this domain is

Not "how to run a query" but **how to keep running them without a surprise bill or a silent
failure**. Two halves, and both reduce to a threshold you have to choose deliberately.

## 2. Cost — two crossovers, computed

**On-demand bills WORK DONE. Capacity bills TIME RESERVED.** A reservation costs the same
saturated or idle, which is why comparing them per-query is the wrong frame.

```
100 Enterprise slots, always on  =  $4,380 / month
crossover with on-demand         =  702 TiB scanned / month
with a 3-year commitment         =  421 TiB
```

Below the crossover you are paying for idle slots; above it you are paying a premium for elasticity
you are not using. In practice most estates want **both** — a baseline reservation for the steady
load, with autoscaling or on-demand absorbing peaks. Sizing a reservation for the *peak* is how
people end up paying for idle slots all night.

**Storage has two levers, and one is free:**

| lever | effect |
|---|---|
| **long-term storage** | **50% off**, automatic after 90 days *untouched* |
| **physical billing** | wins above **2.0×** compression — analytical data is usually 3–5× |

Long-term pricing triggers on **not being modified**, not on not being read. So a pipeline that
rewrites a whole table daily keeps every byte at active pricing forever, while the same data as
date partitions — where only today's partition changes — lets everything older age into the
discount.

> **Partitioning is a storage-cost decision as well as a query-cost one**, which is not obvious
> from either price list.

**Only four things actually prevent spend:** `require_partition_filter`, `maximum_bytes_billed`,
custom quotas, and a reservation ceiling. **A budget alert is a notification** — by the time it
fires the money is gone, and it is routinely mistaken for a cap.

## 3. Monitoring — the condition matters more than the threshold

Measured on the trip stream's real hourly seasonality, with four genuine outages injected:

| approach | alerts | false | precision |
|---|---|---|---|
| best **static** threshold | 91 | 87 | **4%** |
| best **seasonal** baseline | 10 | 6 | **40%** |

Same data, same incidents, same alerting system. **A 10× difference in precision from changing
what the number is compared against.**

The cause is in the metric: its **busiest hour is 21× its quietest**. A normal quiet hour and a
normal busy hour differ by more than an outage differs from normal — so no single number can
separate "quiet" from "broken". That is not a tuning problem; it is the wrong condition.

**The general rule: alert on a metric that is already normalised.** Error *rate* not error count.
Latency *percentile* not mean. Freshness *lag* not row count.

**For a data pipeline specifically, alert on freshness** — time since the last successful load. One
number, no seasonality, and it catches the failure mode that job status misses: a job that succeeds
while processing nothing does not change its status, but it does change its lag.

## 4. What was actually run

| | |
|---|---|
| `01_cost/bigquery_economics.py` | ✅ **fully executed** — arithmetic |
| `02_monitoring/alerting_thresholds.py` | ✅ **fully executed** — real seasonality |
| Reservations, Cloud Monitoring, log sinks | 📝 **write-only** |

Prices are approximate US multi-region list prices and **move**. The crossovers are the deliverable,
not the digits — re-run with current numbers before quoting them.
