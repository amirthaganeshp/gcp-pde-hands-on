# Dataform (and BigQuery Pipelines)

> **Domains 3 + 5** · Success Guide pp. 60–64 · Ultimate §1.8
> **Runtime:** ~3 s (much longer on a first run — npx fetches the CLI) · **Needs:** node + npx

```bash
python 03_bigquery/02_dataform/compile_check.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

> ✅ **The DAG is compiled and verified locally. Nothing is ever deployed.**
> `dataform compile` resolves names and dependencies **offline** — no BigQuery connection, no
> credentials, no SQL executed. `defaultProject` is a placeholder string.

---

## 1. What it is

**Dataform manages complex SQL transformations inside BigQuery**, with software-engineering
practice applied to them. It is the answer to "spaghetti SQL": a pile of scheduled queries with
dependencies that exist only in someone's head.

| it gives you | which replaces |
|---|---|
| **Version control** — native Git (GitHub, GitLab, Bitbucket) | SQL pasted into the console |
| **Automatic dependency DAG** — inferred from how tables reference each other | hand-maintained run order |
| **Assertions** — data quality tests that run *before* production sees the data | discovering it in the dashboard |
| **Environment management** — same code to dev, qa, prod | copy-pasted queries with edited dataset names |
| **Serverless orchestration** | an Airflow DAG you didn't need |

## 2. Components

| component | what it is |
|---|---|
| **Repository** | The Git-backed project. |
| **Workspace** | Your development branch of it. |
| **SQLX file** | SQL plus a `config {}` block. The unit of definition. |
| **`ref()`** | How one table references another — **this is what builds the DAG**. |
| **Declaration** | Registers an external source table so it can be `ref()`-ed. |
| **Assertion** | A test: uniqueness, non-null, row conditions, or custom SQL. |
| **Tag** | Labels for running a subset of the graph. |
| **Release / workflow config** | Scheduled compilation + execution. |

## 3. Fundamental operations

```sql
-- definitions/trips_daily.sqlx
config {
  type: "table",
  schema: "analytics",
  description: "One row per station per day",
  assertions: {
    uniqueKey: ["trip_date", "start_station"],
    nonNull: ["trip_date", "start_station", "trips"]
  },
  bigquery: {
    partitionBy: "trip_date",
    clusterBy: ["start_station"]
  }
}

SELECT
  DATE(event_time)        AS trip_date,
  start_station,
  COUNT(*)                AS trips,
  AVG(duration_min)       AS avg_duration_min
FROM ${ref("trips_raw")}      -- <- the dependency edge
WHERE duration_min > 0
GROUP BY trip_date, start_station
```

**`${ref("trips_raw")}` does two things at once**: it resolves to the fully-qualified table name
*for the current environment*, and it tells Dataform that this table depends on that one. You never
declare the DAG separately, which is why it cannot drift from the code.

| `type:` | produces |
|---|---|
| `table` | a full rebuild |
| `view` | a logical view |
| `incremental` | appends/merges only new rows — with a `WHERE` guarded by `when(incremental(), …)` |
| `operations` | arbitrary DDL/DML |
| `assertion` | a standalone test |

## 4. BigQuery Pipelines — the UI layer

A visual, console-based orchestration feature **powered by Dataform underneath** but abstracting
the repository away. Unlike plain Dataform (strictly SQLX), it can sequence a wider set of assets:

- **SQL queries** (saved scripts)
- **Notebooks** (Colab Enterprise) — so a Python ML step sits in the same graph
- **Data preparations** (UI cleaning steps)
- **SQLX tasks** — tables, views, sources, assertions

**Authentication:** user credentials (preview) or — for production, and **required** for triggering
via the Dataform API rather than the UI — a **service account** with least privilege.

**Sharing is all-or-nothing:** you grant access to a *pipeline*, never to individual tasks in it.

### Limitations worth knowing

- **Console only** — the pipeline builder does not exist outside the Cloud Console UI.
- **Region is immutable** — to change it you recreate the pipeline.
- **All referenced datasets must be in the same location**, or the pipeline fails outright.

## 5. Nuances — the part worth reading

**Assertions are the reason to choose this over scheduled queries.** A scheduled query that
produces wrong numbers succeeds. An assertion fails the run *before* the reporting table is
published.

**Dataform orchestrates SQL inside BigQuery; Composer orchestrates services.** If the DAG is
entirely "one BigQuery table depends on another", Composer is over-engineering — and if the DAG
spans Dataflow, GCS and an external API, Dataform cannot express it.

**Incremental models are where correctness goes wrong.** The incremental predicate must be
idempotent — a re-run over an overlapping window must not duplicate rows. `MERGE`-shaped logic
on a business key, not a blind append.

## 6. When to use it — and when not

| situation | reach for |
|---|---|
| multi-step SQL DAG, version control, tests | **Dataform** |
| one recurring statement | **BigQuery scheduled query** |
| the graph spans several services | **Composer** |
| visual, low-code, notebooks in the graph | **BigQuery Pipelines** |
| ad-hoc visual exploration | **Data Canvas / Dataprep** |

## 7. What was actually run

A **real Dataform project** lives in [`dataform/`](dataform/) — a declaration, a view, a table
with assertions, an incremental model and a hand-written assertion. `compile_check.py` compiles it
and reports the resolved graph.

| | |
|---|---|
| `compile_check.py` | ✅ **fully executed**, exit 0 |
| CLI | `@dataform/cli@3.0.0`, fetched by npx and cached |
| **Measured** | **6 actions**, **0 errors**, **3 dependency edges** — every edge resolved from a `ref()` |
| BigQuery connections | **0** — `defaultProject` is a placeholder |
| Credentials | **none** |

**The check has teeth, and that is demonstrated rather than claimed.** The script copies the
project, changes `ref("stg_trips")` to `ref("stg_trip")` — one missing letter — and compiles the
copy:

```
CAUGHT: 2 compilation error(s).
  trips_daily.sqlx: Could not resolve "stg_trip"
  trips_daily.sqlx: Missing dependency detected: ... depends on "stg_trip" which does not exist
```

📝 **Documented, not demonstrated:** `dataform run`, assertions actually executing, Git
integration, release configurations, workflow schedules, BigQuery Pipelines and the Gemini agent.
**A clean compile means the graph is sound — not that the pipeline is correct.**

> `gcloud dataform` does **not** exist in older SDKs. The npx CLI is the working path.
