# Managed Service for Apache Spark

> **Domain 2 — Ingesting and Processing the Data (25%)** · Success Guide pp. 93–104 · Ultimate §2.4

> **Formerly Dataproc.** Google merged Dataproc (clusters) with Serverless for Apache Spark into
> one product with two deployment models. **The API is unchanged** — `dataproc.googleapis.com`,
> `gcloud dataproc`. See [`99_reference/SERVICE_NAMES.md`](../99_reference/SERVICE_NAMES.md).

| service | covers | state |
|---|---|---|
| [`01_spark/`](01_spark/) | lazy evaluation, the shuffle, skew and salting, broadcast joins, caching | ✅ built |
| [`02_data_fusion/`](02_data_fusion/) | visual pipelines, Wrangler recipes, **macros**, runs on Dataproc | 📝 documented |
| [`03_dataprep/`](03_dataprep/) | **the five sampling modes**, recipes, pushdown to BigQuery/Dataflow | 📝 documented |

---

## Why all three are here

They are the **non-Beam ways to process data**. Dataflow gets its own section because it is a
programming model; these three are alternatives to it, and the exam mostly asks you to choose
between them.

| if... | then |
|---|---|
| existing Spark or Hadoop, minimal change | **Managed Spark** |
| new streaming work, no cluster concept wanted | **Dataflow** — see [`../02_beam_dataflow/`](../02_beam_dataflow/) |
| non-engineers need to build pipelines visually | **Data Fusion** |
| interactive data cleaning, profiling first | **Dataprep** |
| it is SQL over data already in BigQuery | **BigQuery** — no engine at all |

## The one number to remember

`spark.sql.shuffle.partitions` defaults to **200**, whatever your data looks like. Measured here:
a `groupBy` producing **8 groups** spread across **200 partitions** — 192 empty, each with a task.

Spark's cost is almost entirely the **shuffle**. Narrow transformations are free; wide ones are
not; and one hot key turns a wide step into a single-core job however large the cluster — measured
at a **34.5×** partition imbalance.
