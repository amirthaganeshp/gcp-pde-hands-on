# Cloud Logging

> **Domain 5 — Maintaining and Automating Workloads (18%)** · Success Guide pp. 115–117 · Ultimate §5.4
> 📝 **Write-only** — a managed service; nothing to run locally.

---

## 1. What it is

The central log store. Everything on GCP writes here by default, and the data-engineering job is
usually **routing** it: what to keep, where to put it, and for how long.

## 2. Components

| component | what it is |
|---|---|
| **Log entry** | A structured record — resource, severity, timestamp, `jsonPayload`. |
| **Log bucket** | Where entries are stored. `_Default` and `_Required` exist automatically. |
| **Sink** | A **filter + destination**. The routing primitive. |
| **Log-based metric** | A counter or distribution derived from matching entries — **this is the bridge into Cloud Monitoring and alerting**. |
| **Log Analytics** | SQL over log buckets, queryable from BigQuery. |
| **Exclusion** | A filter that **drops** entries before they are stored (and billed). |

## 3. The four audit log types

| | contains | on by default? |
|---|---|---|
| **Admin Activity** | configuration and metadata changes | **yes, and cannot be disabled** |
| **Data Access** | reads/writes of *user data* | **no** — must be enabled, and is **high volume** |
| **System Event** | Google-initiated actions | yes |
| **Policy Denied** | access refused by a policy | yes |

> **Data Access logs are the exam's compliance answer and the real-world cost trap.** They are what
> proves *who read the PII table*, and they can dwarf every other log source in volume. Enable
> deliberately, scoped, with an exclusion or a short retention on the noisy parts.

## 4. Sinks — the routing decision

| destination | for |
|---|---|
| **Cloud Storage** | long-term compliance archive; pair with lifecycle → Coldline/Archive |
| **BigQuery** | **analytics on logs** — usage patterns, error trends, cost attribution |
| **Pub/Sub** | forward to a SIEM or a third-party tool, or trigger a pipeline |
| **Another log bucket** | consolidate across projects |

```bash
gcloud logging sinks create bq-audit \
    bigquery.googleapis.com/projects/PROJECT/datasets/audit \
    --log-filter='protoPayload.serviceName="bigquery.googleapis.com"'
```

**Aggregated sinks at the folder or organization level** capture every project underneath,
including ones created later. That is how a compliance requirement gets met once instead of
per-project.

## 5. Nuances — the part worth reading

**Creating a sink does not stop the logs being stored.** Routing and retention are separate: a sink
*copies* matching entries to the destination while `_Default` keeps them too. Reducing cost needs
an **exclusion** or a shorter bucket retention — not a sink.

**The sink's writer identity needs permission on the destination.** `gcloud` prints a service
account when the sink is created, and it must be granted (for example)
`roles/bigquery.dataEditor`. Forgetting this is the commonest "my sink isn't working".

**Log-based metrics are how logs become alerts.** A regex over error text becomes a counter,
a counter becomes an alerting condition — which is the path from "the pipeline logged a failure"
to "someone was paged". See [`../02_monitoring/`](../02_monitoring/).

**Default retention is 30 days** in `_Default`. Anything needed for compliance must be routed
somewhere durable *before* that, and archived logs are not something you can retroactively
recover.

## 6. When to use what

| you need | use |
|---|---|
| keep audit logs 7 years, cheaply | **sink → GCS** + lifecycle to Archive |
| analyse error rates and usage in SQL | **sink → BigQuery**, or **Log Analytics** |
| feed a SIEM | **sink → Pub/Sub** |
| alert on a log pattern | **log-based metric** + alerting policy |
| cut log spend | **exclusion filters**, shorter retention |
| prove who read a table | **Data Access audit logs** (enable first) |

## 7. What was actually run

**Nothing.** Cloud Logging has no local equivalent and nothing here simulates one. The
**alerting statistics** it ultimately feeds are measured in [`../02_monitoring/`](../02_monitoring/)
— static thresholds at **4%** precision against seasonal ones at **40%**.
