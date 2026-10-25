# Composer — what the illustration shows

The README explains the *service*. This file explains the *DAG*: what it sets up, what running it
proved, and which exam idea each result makes concrete.

---

## `dags/trips_daily.py`

**Setup:** real Apache Airflow **3.3.2**, local, SQLite metadata DB, in its **own virtualenv**
(`~/venvs/airflow`). Same DAG code Composer would run.

```bash
~/venvs/airflow/bin/airflow dags test trips_daily 2026-06-05
~/venvs/airflow/bin/airflow dags test trips_daily 2026-06-03
```

### The shape

```
extract -> check_volume (branch)
                |-- enough rows --> transform --> load --> MERGE --+
                |-- too few ------> skip_load -------------------+ |
                                                                 v v
                                                               report
```

`report` carries **`TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS`**, and that one line is what the whole
DAG exists to demonstrate.

### What running it twice proved

| logical date | rows | path taken | `report` | outcome |
|---|---|---|---|---|
| `2026-06-05` | 4,812 | `transform → load → MERGE` | **ran** | **success** |
| `2026-06-03` | 12 | `skip_load` | **ran** | **success** |

> **These row counts are hardcoded in the DAG, not read from `data/`.** `validate` returns
> `4_812` for every date except `2026-06-03`, which returns `12`, purely to force each branch.
> They are **not** measured from the trips dataset. What *was* measured is the path each run took
> and its outcome.

**Both branches were executed for real** — not described, not one path tested twice.

## The trap this is about

A branch marks the *untaken* path `Skipped`. With the default `all_success`, **everything
downstream of the skip is skipped too — including the join task that should still run.** The
pipeline reports success while quietly doing nothing, which is the worst failure mode an
orchestrator has.

| rule | fires when | use |
|---|---|---|
| `all_success` *(default)* | all upstreams succeeded | the normal case |
| `none_failed` | all succeeded **or were skipped** | basic branch joins |
| **`none_failed_min_one_success`** | none failed **and at least one actually ran** | **the correct branch-join rule** |
| `all_done` | everything finished, pass or fail | "notify at the end" |

`none_failed` alone would also fire if *every* upstream were skipped. The `min_one_success` variant
insists something real happened.

## The caveat found by running it

**`airflow dags test` collapses the data interval.** The window the run reported is not the window
a scheduled run would use.

> That is recorded in the DAG's own docstring rather than quietly ignored, because the data
> interval is exactly the concept the DAG is teaching — **a run labelled `2026-06-05` processes
> that day's data, whenever it happens to execute**. Getting it wrong produces a pipeline that is
> silently always one day off, and `dags test` is not the tool that will reveal it.

## The environment mistake worth recording

Airflow went into the Beam virtualenv and **broke Beam**: `cryptography 50.0.1` against Beam's
`<49`, and `grpcio 1.83.1` against `grpcio-status`'s `>=1.84`. Repairing it meant removing Airflow
plus five orphaned providers and restoring pins until `pip check` was clean.

> **The plan for this repo already said to keep them in separate venvs.** The failure was not
> knowing the wrong thing — it was not following what was already written down. Hence
> `~/venvs/airflow`, and hence the note at the top of the README.

## What running locally cannot show

Not demonstrated, and not simulated: the GKE and Cloud SQL environment internals, queue-depth
autoscaling, environment sizes, the GCS DAG-sync mechanism, deferrable operators under real
concurrency, and Composer's own IAM.

The **scheduling semantics** — which is what the exam actually tests — are identical, because this
is the same Airflow.
