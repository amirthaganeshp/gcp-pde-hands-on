# Monitoring and alerting

> **Domain 5 — Maintaining and Automating Workloads (18%)** · Success Guide pp. 115–117 · Ultimate §5.4
> **Runtime:** ~1 s · **Needs:** nothing — pure Python

```bash
python 11_ops_cost_monitoring/02_monitoring/alerting_thresholds.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

---

## 1. What it is

Cloud Monitoring collects metrics, draws dashboards, and fires **alerting policies** when a
condition holds. The service is straightforward; **choosing the condition is the entire skill**,
and that is what the illustration measures.

**Measured:** against a seasonal workload,

| alerting strategy | precision |
|---|---|
| a **static threshold** | **4%** |
| a **seasonally-aware** threshold | **40%** |

> **Ten times fewer false alarms for the same real incidents.** A static threshold on a metric with
> a daily cycle does not alert on problems — it alerts on **lunchtime**.

## 2. Components

| component | what it is |
|---|---|
| **Metric** | A time series. Google-supplied, or custom/log-based. |
| **Metric type** | **gauge** · **delta** · **cumulative** · **distribution** — see below. |
| **Alignment / reduction** | How raw points are bucketed, then combined across series. |
| **Condition** | Threshold + **duration window** + aggregation. |
| **Duration window** | How long the breach must persist before firing. |
| **Notification channel** | Email, Slack, PagerDuty, Pub/Sub, webhook. |
| **Uptime check** | External probe of an endpoint. |
| **SLO / error budget** | Objective plus the allowance for falling short of it. |

### Metric types, and why it matters

| type | is | example |
|---|---|---|
| **Gauge** | a value *now* | queue depth, CPU |
| **Delta** | change during the interval | bytes in the last minute |
| **Cumulative** | a monotonic running total | total requests since start |
| **Distribution** | a **histogram** per interval | request latency |

> **Alert on a distribution *percentile*, never a mean.** A mean latency of 200 ms is compatible
> with 1% of users waiting 10 seconds. p95/p99 is the user's experience; the mean is nobody's.

## 3. The metrics worth alerting on

| signal | condition | what it means |
|---|---|---|
| **Pub/Sub `oldest_unacked_message_age`** | > N minutes | consumer lag or a crashing subscriber — **the single best streaming health signal** |
| **Pub/Sub subscription backlog** | growing | consumers cannot keep up |
| **Dataflow system lag / watermark** | rising | a hot key or a slow external call |
| **Dataflow backlog bytes** | rising | ingestion outpacing processing |
| **BigQuery slot utilisation** | pinned at 100% | queries are being throttled |
| **BigQuery job error rate** | > x% over N min | a pipeline is failing |
| **Billed bytes** | spike | someone shipped a `SELECT *` |
| **Composer task failures / queue depth** | non-zero, rising | the orchestrator is behind |

## 4. Nuances — the part worth reading

**Duration windows remove flapping but have a floor.** Requiring N consecutive breaches stops a
single spike paging someone. **But a window longer than your incidents cannot see them** — a
5-minute window over a 3-minute outage is a policy that never fires. Kept in
`99_reference/FINDINGS.md` as an honest negative.

**Alert on symptoms, not causes.** "Oldest unacked message > 10 minutes" is user-visible. "CPU >
80%" is not a problem — it may be exactly what you are paying for.

**`INFORMATION_SCHEMA` is retrospective; Cloud Monitoring is proactive.** Both are legitimate;
the exam distinguishes them by *timing*.

| you need | use |
|---|---|
| "which query cost the most last month?" | **`INFORMATION_SCHEMA.JOBS`** |
| "tell me the moment the error rate exceeds 5%" | **an alerting policy** |
| "why did this query starve the others at 14:03?" | **`JOBS_TIMELINE`** |
| "keep audit logs for seven years" | **a logging sink** |

**An alert nobody acts on is worse than no alert**, because it trains people to ignore the channel.
The 4%-precision policy above is that failure mode, quantified.

## 5. What was actually run

| | |
|---|---|
| `alerting_thresholds.py` | ✅ **fully executed** — synthetic seasonal series with injected incidents, precision computed both ways |
| Cloud resources | **none** |

📝 **Documented, not demonstrated:** Cloud Monitoring itself, notification channels, uptime checks,
SLOs. The script models **the statistics of choosing a threshold**, which is the part that is
actually hard, and does not pretend to be the product.
