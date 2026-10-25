# BigQuery and the analytical layer

> **Domains 3 + 4 (20% + 15%)** · Success Guide pp. 34–67 · Ultimate §3.4

The largest topic on the exam. `bigquery` appears **166 times** in the 117-page guide — more than
`dataflow`, `pub/sub`, `composer` and `dataproc` combined.

| service | covers | state |
|---|---|---|
| [`01_bigquery/`](01_bigquery/) | architecture, partitioning, clustering, cost, pricing models, views, BI Engine, ingestion paths, `INFORMATION_SCHEMA` | ✅ **built** |
| [`02_dataform/`](02_dataform/) | SQLX, `ref()` dependency graphs, assertions, BigQuery Pipelines | ✅ **compiles locally** |
| [`03_biglake/`](03_biglake/) | external tables vs BigLake vs Omni, connection delegation | 📝 documented |

---

## The decision this section exists to make

**"How much of the table does this query have to read?"** On-demand BigQuery bills exactly that, so
every design choice — partition key, cluster keys, column list, view vs materialized view — is a
different answer to that one question.

[`01_bigquery/partition_pruning.py`](01_bigquery/) measures the three levers, and they multiply:

| lever | measured |
|---|---|
| column projection — 2 columns instead of 10 | **11.8×** less |
| partition pruning — 1 day of 14 | **13.3×** less |
| block pruning — clustered vs not | **6.2×** vs **1.0×** |

A narrow `SELECT` on a filtered partition of a well-clustered table can be orders of magnitude
cheaper than the `SELECT *` that returns the same answer.

## Why Dataform is here and not in `05_orchestration`

Dataform orchestrates **SQL inside BigQuery**; Composer orchestrates **services**. Putting them
together implies they compete, and they do not — a realistic stack uses Composer to trigger a
Dataform run, and Dataform to sequence the two hundred SQL transforms inside it.

## What is simulated, and what is not

There is **no official local BigQuery emulator**, so this section is deliberate about which claim
is which:

- **📝 Real SQL, never submitted** — `bigquery_patterns.sql`. Correct, and runs unmodified in the
  free sandbox.
- **🔬 Labelled simulation** — `partition_pruning.py` measures **Parquet**, which is columnar with
  per-block min/max statistics just as BigQuery is. The mechanism transfers; the numbers do not.
- **Never** — a DuckDB or Parquet query presented as a BigQuery query.
