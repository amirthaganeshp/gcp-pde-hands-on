# Orchestration

> **Domain 5 — Maintaining and Automating Data Workloads (18%)** · Success Guide pp. 105–114 ·
> Ultimate §5.2, §1.7, §1.9

| service | covers | state |
|---|---|---|
| [`01_composer/`](01_composer/) | Airflow DAGs, data intervals, branching, trigger rules, XCom, sensors | ✅ built |
| [`02_workflows/`](02_workflows/) | YAML steps, connectors, checkpointing, callbacks | 📝 documented |
| [`03_scheduler_eventarc/`](03_scheduler_eventarc/) | cron vs event triggers — the two ways a pipeline starts | 📝 documented |

---

## The decision this section exists to make

**How much orchestration does this actually need?** The options are not equivalent in cost, and
the heaviest one bills continuously.

| if... | then |
|---|---|
| one scheduled query | **BigQuery scheduled query** — no orchestrator at all |
| a linear sequence of API calls | **Workflows** — serverless, no environment |
| dependencies across services, retries, backfill, SLAs | **Cloud Composer** |
| react to an event rather than a clock | **Eventarc** |
| sequence SQL *inside* BigQuery | **Dataform** — in [`../03_bigquery/`](../03_bigquery/) |

**Composer is the heavyweight and it costs money while idle.** Using it to run one daily query is
the most common over-engineering in this domain.

## Why Dataform is not here

Dataform orchestrates **SQL inside BigQuery**; Composer orchestrates **services**. Grouping them
implies they compete. A realistic stack has Composer *trigger* a Dataform run.
