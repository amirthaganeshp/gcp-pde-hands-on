# BigLake, External Tables and BigQuery Omni

> **Domain 3 — Storing the Data (20%)** · Success Guide pp. 41–43 · Ultimate §3.4
> 📝 **Write-only** — all three need cloud storage and a project.

---

## 1. What it is

Three ways to query data that **does not live in BigQuery's native storage**, in increasing order
of capability.

| | data sits in | governance | caching | use when |
|---|---|---|---|---|
| **External table** | GCS or Google Drive | **none of BigQuery's fine-grained controls** | **no** | quick exploration of lake files |
| **BigLake table** | GCS, **S3, Azure Blob** | **full — row-level, column-level via policy tags, masking** | yes | data must stay in the lake but still be governed |
| **Omni** | **AWS / Azure**, compute runs *there* | full | — | data legally or economically cannot move |

**BigLake is the modern evolution of the external table**, and the difference is the whole point:
an external table cannot carry a policy tag; a BigLake table can.

## 2. Components

| component | what it is |
|---|---|
| **Connection resource** | The credential BigQuery uses to reach the object store. **BigLake's key idea:** users are granted access to the *table*, not to the bucket. |
| **Supported formats** | CSV, JSON (newline-delimited), Avro, Parquet, ORC; Iceberg and Delta for BigLake. |
| **Hive partitioning** | Directory layout (`dt=2026-06-09/`) read as partition columns. |
| **Metadata cache** | Optional, for BigLake — avoids re-listing millions of objects per query. |
| **Omni region** | The AWS/Azure region where the query physically executes. |

## 3. Fundamental operations

```sql
-- An EXTERNAL table: no connection, no fine-grained security
CREATE OR REPLACE EXTERNAL TABLE `ds.trips_ext`
OPTIONS (
  format = 'PARQUET',
  uris = ['gs://my-lake/trips/*.parquet']
);

-- A BIGLAKE table: note the WITH CONNECTION - that is the difference
CREATE OR REPLACE EXTERNAL TABLE `ds.trips_biglake`
WITH CONNECTION `us.my-lake-connection`
OPTIONS (
  format = 'PARQUET',
  uris = ['gs://my-lake/trips/*.parquet'],
  max_staleness = INTERVAL 1 HOUR,
  metadata_cache_mode = 'AUTOMATIC'
);
```

**Delegation is the mechanism.** With BigLake the *connection's* service account reads the bucket.
An analyst who can query the table still cannot `gcloud storage ls` the underlying files — which is
precisely what an external table cannot give you.

## 4. Nuances — the part worth reading

**The exam's giveaway phrasing:**

| the scenario says | the answer is |
|---|---|
| "keep data in GCS **but apply column-level security**" | **BigLake** |
| "data is in **S3/Azure** and cannot move (compliance or **egress cost**)" | **Omni** |
| "quick look at some CSVs in a bucket" | **external table** |
| "we query it constantly and want it fast and cheap" | **load it natively** |

**Omni runs the query where the data is.** Compute executes in the AWS/Azure region and **only
results cross the boundary** — that is what avoids the egress bill, and why it is the answer to
"cannot move the data".

**External tables have no caching and no fine-grained security.** Both absences are tested.

**Performance is not free.** Native storage is columnar, statistics-rich and clustered; an external
table reads whatever the lake files happen to be. Poor file layout — millions of small objects — is
the usual cause of a slow external query, and the metadata cache exists for exactly that.

**Materialized views cannot be built over external tables** — a restriction that catches people
trying to accelerate a lake query the easy way. Over **BigLake** on S3, however, MV **replicas**
are supported, which is how you localise access and avoid repeated egress.

## 5. When to use it — and when not

**Use external/BigLake when** the data genuinely must remain in object storage — a shared lake,
another team's pipeline output, or a compliance boundary.

**Don't** when you query it heavily and could simply load it. Native storage is cheaper to query,
faster, and fully featured. "Leave it in GCS" is a decision with an ongoing performance cost.

## 6. What was actually run

**Nothing.** All three require a project, a bucket and — for Omni — another cloud entirely. The
**mechanism** they rely on, columnar block pruning, is what
[`../01_bigquery/partition_pruning.py`](../01_bigquery/) measures locally against Parquet.
