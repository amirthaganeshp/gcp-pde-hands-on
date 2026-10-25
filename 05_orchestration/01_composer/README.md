# Cloud Composer (Apache Airflow)

> **Domain 5 — Maintaining and Automating Workloads (18%)** · Success Guide pp. 105–114 · Ultimate §1.9
> **Runtime:** ~10 s · **Needs:** its own venv — `~/venvs/airflow`

```bash
~/venvs/airflow/bin/airflow dags test trips_daily 2026-06-05
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

> **Airflow gets its own virtualenv, deliberately.** Airflow and Beam have genuinely incompatible
> pins (`cryptography`, `grpcio`). Installing Airflow into the Beam venv broke Beam here once.

---

## 1. What it is

**Composer is managed Apache Airflow** — which is why this runs locally: same DAGs, same
operators, same scheduler semantics.

Airflow's job is **dependency and schedule management**, not data processing. It decides *when*
things run and *in what order*; the work itself belongs in BigQuery, Dataflow or Spark.

## 2. Anatomy of an environment

| piece | what it does |
|---|---|
| **GCS bucket** | **The deployment mechanism.** You drop DAGs, plugins and dependencies here and Composer syncs them to workers and scheduler. |
| **Scheduler** | Decides what should run and queues tasks. |
| **DAG processor** | Parses the Python files — **separated from the scheduler** in modern Composer so heavy DAG code can't starve scheduling. |
| **Workers** | Kubernetes pods that pull from the queue and execute. |
| **Metadata DB (Cloud SQL)** | Task state, history, XComs, configuration. |

Composer 3 abstracts it, but underneath it is **GKE + Cloud SQL**. **Deploying a DAG is a file
copy** — that is the whole CI/CD story.

## 3. The Airflow vocabulary

| term | what it is |
|---|---|
| **DAG** | The graph, plus its schedule. |
| **Operator** | *What* a task does — `BigQueryInsertJobOperator`, `DataflowStartFlexTemplateOperator`, `PythonOperator`. |
| **Task** | An operator instantiated inside a DAG. |
| **Task Instance (TI)** | One *run* of a task for one logical date. |
| **Sensor** | A task that **waits** for a condition — a file landing, a partition existing. |
| **Data interval** | The window of *data* a run covers. **Not "now".** |
| **XCom** | Small key-value payloads passed between tasks via the metadata DB. |
| **Trigger rule** | When a task runs given its upstreams' states. Default `all_success`. |
| **Task Group** | Visual/logical grouping. **Replaced SubDAGs**, which were buggy and slow. |
| **Pool / priority** | Concurrency limits across DAGs. |

**Task Instance states:** `None` → `Queued` → `Running` → `Success` / `Failed` /
`Upstream_Failed` (a parent failed) / `Skipped` (branching bypassed it).

## 4. Branching and trigger rules

`BranchPythonOperator` (or `@task.branch`) returns the **task_id** of the path to take.

> **The cascading-skip trap:** a skipped branch makes every downstream task `Skipped` too —
> including the join task that should still run. The default `all_success` will not fire it.

| trigger rule | fires when |
|---|---|
| `all_success` *(default)* | every upstream succeeded |
| `all_done` | every upstream finished, pass or fail — **the "notify at the end" rule** |
| `all_failed` | every upstream failed |
| `one_success` | at least one succeeded, without waiting for the rest |
| `none_failed` | all succeeded **or were skipped** — essential with branching |
| **`none_failed_min_one_success`** | **the branch-join rule used here** |

**Measured** — the same DAG run on two dates, taking opposite branches:

| logical date | rows | path taken | outcome |
|---|---|---|---|
| `2026-06-05` | 4,812 | `transform → load → MERGE` | **success** |
| `2026-06-03` | 12 | `skip_load` | **success** |

> **These row counts are hardcoded in the DAG, not read from `data/`.** `validate` returns
> `4_812` for every date except `2026-06-03`, which returns `12`, purely to force each branch.
> They are **not** measured from the trips dataset. What *was* measured is the path each run took
> and its outcome.

The join task ran in **both** cases, which is exactly what the trigger rule is for.

## 5. Autoscaling

**Composer scales on Celery queue depth** — not CPU, not data backlog. Tasks pile up ⇒ new
worker pods; queue empties ⇒ pods terminate.

| parameter | effect |
|---|---|
| `--min-workers` / `--max-workers` | hard bounds. **Set the max** or one buggy DAG spawns workers until the budget is gone. |
| `celery.worker_concurrency` | simultaneous tasks per worker pod |
| Environment size (Small/Medium/Large) | baseline CPU/RAM for scheduler, web server, DB |

It has far fewer tuning knobs than Dataflow, and that is appropriate: **Composer decides when
jobs run; Dataflow processes the bytes.**

## 6. Troubleshooting

| symptom | cause | fix |
|---|---|---|
| **Zombie tasks** | worker pod died (usually OOM) or lost the Cloud SQL connection | raise worker memory |
| **DAG parse timeouts, high scheduler CPU** | heavy logic, API calls or DB lookups in **top-level** code, re-executed every parse | move all work **inside** an operator's execution function |
| **XCom size exceeded** | passing a DataFrame between tasks | **anti-pattern** — write to GCS, pass the `gs://` URI |
| **Sensor deadlock** | N sensors occupy all N worker slots, so nothing else can start | `mode='reschedule'` — releases the slot between checks |

## 7. Nuances — the part worth reading

**A DAG run is about a data interval, not about now.** A run labelled `2026-06-05` processes
*that day's* data, whenever it actually executes. Getting this wrong produces a pipeline that is
silently always one day off.

> **Caveat from the actual run:** `airflow dags test` **collapses the data interval**, so the
> window it reports is not what a scheduled run would use. Recorded in the DAG's docstring rather
> than quietly ignored.

**Idempotency is mandatory, because Airflow retries.** A task that crashes halfway will be run
again. Use `MERGE` rather than `INSERT`, or a retry duplicates the data.

**Keep top-level code trivial.** The scheduler re-parses every DAG file every few seconds. A
database call at module scope is executed on every one of those parses.

**Dynamic DAG generation** is just Python — loop over a config in GCS to build tasks for fifty
tables. Same caveat: the loop runs at **parse** time, so it must be cheap.

**Deferrable operators** free their worker slot while waiting, which is the structural fix for the
sensor-deadlock problem above.

## 8. When to use it — and when not

| situation | reach for |
|---|---|
| dependencies across several services, retries, backfill | **Composer** |
| 50+ dependencies, complex branching | **Composer** |
| a single scheduled query | **BigQuery scheduled query** — no orchestrator needed |
| a linear chain of API calls | **Workflows** — serverless, no environment to pay for |
| event-driven, not scheduled | **Eventarc** + Cloud Run |
| sequencing SQL *inside* BigQuery | **Dataform** |

**Composer bills continuously** — an environment is always on. Using it for one daily query is
this domain's signature over-engineering.

## 9. What was actually run

| | |
|---|---|
| `dags/trips_daily.py` | ✅ **fully executed**, both branches, exit 0 — row counts are hardcoded stand-ins, not read from `data/` |
| Airflow | **3.3.2**, local, SQLite metadata DB |
| Cloud resources | **none** |

📝 **Documented, not demonstrated:** GKE/Cloud SQL environment internals, queue-depth
autoscaling, environment sizes, deferrable operators in anger, Composer's GCS DAG sync.
