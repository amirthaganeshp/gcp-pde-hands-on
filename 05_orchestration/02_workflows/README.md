# Cloud Workflows

> **Domain 5 — Maintaining and Automating Workloads (18%)** · Success Guide §11.10
> 📝 **Write-only** — serverless, no local runtime. Nothing here was executed.

---

## 1. What it is

A **fully managed, serverless orchestration engine** that chains Google Cloud services, Cloud Run
services and external HTTP APIs into one process.

**The contrast that defines it:** Composer is built for heavy, distributed *data* pipelines;
Workflows is built for **low-latency microservice orchestration and API glue**. Workflows has no
environment to provision and **scales to zero** — Composer bills continuously.

## 2. Components

| component | what it is |
|---|---|
| **Workflow** | A definition in **YAML or JSON** — declarative, not Python. |
| **Step** | The unit of execution. Assigns variables, calls APIs, parses responses. |
| **Connector** | Native GCP connectors that handle auth, request formatting and **polling for long-running operations** — no OAuth boilerplate. |
| **Execution** | One run. **Every step is checkpointed**, so state survives a failed downstream call. |
| **Callback** | A generated URL an external system pings. Can wait **up to one year**. |

## 3. Fundamental operations

| capability | syntax |
|---|---|
| Control flow | `switch`, conditional expressions |
| Error handling | **`try` / `except` built into the language**, with fallback routines |
| Retries | per-step policies — backoff interval, max attempts, exception filters |
| Waiting | native polling, or **HTTP callbacks** for human/external intervention |
| Parallelism | steps can run sequentially, conditionally, or in parallel |

```yaml
- run_query:
    call: googleapis.bigquery.v2.jobs.query
    args:
      projectId: ${project}
      body:
        query: "SELECT COUNT(*) FROM `ds.trips`"
        useLegacySql: false
    result: query_result
```

## 4. Triggers — how a workflow starts

**Workflows has no internal cron.** It is invoked by something else:

| trigger | for |
|---|---|
| **Cloud Scheduler** | time-based — this is how you "schedule" a workflow |
| **Eventarc** | event-driven — a file lands, an audit log fires |
| **Direct API / client library** | from application code |
| **Pub/Sub** (via Eventarc or Scheduler) | message-driven |

## 5. Nuances — the part worth reading

**Stateful checkpointing is the feature.** If a downstream API is down, the execution remembers
exactly where it was. You are not rebuilding idempotency by hand for a chain of API calls.

**Connectors are not just convenience** — they poll long-running operations for you. Calling the
same API by raw HTTP means writing that polling loop yourself.

**A one-year callback wait is a legitimate design**, not an abuse: it is how you model human
approval inside an automated process.

## 6. When to use it — and when not

| situation | reach for |
|---|---|
| a linear chain of API calls | **Workflows** |
| microservice glue, real-time, scale-to-zero | **Workflows** |
| human-in-the-loop approval | **Workflows** callbacks |
| 50+ dependencies, backfill, complex branching | **Composer** |
| heavy data processing | **Dataflow / Spark** — Workflows orchestrates, it does not crunch |
| one scheduled SQL statement | **BigQuery scheduled query** |

**The decision rule:** *lightweight API chains* → Workflows. *Data pipeline dependency graphs* →
Composer.

## 7. What was actually run

**Nothing.** There is no local Workflows runtime, and this repository does not simulate one.
Everything above is documented from the guides and Google's reference.
