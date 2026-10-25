# Monitoring — what the illustration shows

The README explains the *service*. This file explains the *script*: what it simulates, what it
measures, and why the result is about statistics rather than about Cloud Monitoring.

---

## `alerting_thresholds.py`

**Setup:** the trip stream's **real hourly seasonality**, with **four genuine outages injected** at
known times. The script then evaluates two alerting strategies against that known ground truth and
scores each one's precision.

| approach | alerts fired | false alarms | precision |
|---|---|---|---|
| best **static** threshold | 91 | 87 | **4%** |
| best **seasonal** baseline | 10 | 6 | **40%** |

**Same data. Same incidents. Same alerting system.** A **10× difference in precision** from
changing only what the number is compared against.

## Why the static threshold cannot work

The metric's **busiest hour is 21× its quietest**.

> A normal quiet hour and a normal busy hour differ **by more than an outage differs from normal**.
> No single number can separate "quiet" from "broken", so there is no threshold to tune. **It is
> the wrong condition, not a badly chosen one.**

Note these are the *best* thresholds of each kind, found by search — 4% is not a strawman, it is
the ceiling for that approach on this data.

## What 4% precision means in practice

Eighty-seven false alarms against four real incidents. **An alert nobody acts on is worse than no
alert**, because it trains people to ignore the channel — and then the fourth one, the real one,
is ignored too.

## The general rule the numbers point at

**Alert on a metric that is already normalised:**

| not | but |
|---|---|
| error **count** | error **rate** |
| **mean** latency | latency **percentile** (p95/p99) |
| row count | **freshness lag** |

> **A mean latency of 200 ms is compatible with 1% of users waiting 10 seconds.** The mean is
> nobody's experience; the percentile is somebody's. This is why metric *type* matters — a
> distribution can be queried at a percentile, a gauge cannot.

**For a data pipeline specifically, alert on freshness** — time since the last successful load. One
number, no seasonality, and it catches the failure job status misses: **a job that succeeds while
processing nothing** does not change its status, but it does change its lag.

## The honest negative

Duration windows remove flapping — requiring N consecutive breaches stops one spike paging someone.
**But a window longer than your incidents cannot see them.** A 5-minute window over a 3-minute
outage is a policy that never fires, and the script shows that boundary rather than presenting
duration windows as free.

Kept in [`99_reference/FINDINGS.md`](../../99_reference/FINDINGS.md) §7.

## What this cannot show

Not demonstrated, and not simulated: Cloud Monitoring itself, alerting policies, notification
channels, uptime checks, SLOs and error budgets, or log-based metrics.

**The script models the statistics of choosing a condition**, which is the part that is actually
hard and the part a product demo would skip.
