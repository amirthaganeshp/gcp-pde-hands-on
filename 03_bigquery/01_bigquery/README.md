# BigQuery

> **Domains 3 + 4 (20% + 15%)** · Success Guide pp. 34–67 · Ultimate §3.4
> **Runtime:** ~5 s · **Needs:** `pyarrow` — no cloud, no project

```bash
python 03_bigquery/01_bigquery/partition_pruning.py   # the cost mechanics, measured
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

The biggest topic on the exam — `bigquery` appears **166 times** in the 117-page guide — and the
one service here with no official local emulator. What that means is stated plainly in part 10.

---

## 1. What it is

A **serverless columnar OLAP warehouse** whose defining property is that **storage and compute are
separate**. Storage is cheap and always there; compute is summoned per query. No cluster, no node
count.

| piece | name | why you care |
|---|---|---|
| Query engine | **Dremel** | The compute half. Scales independently of storage. |
| Storage | **Colossus** | The distributed file system. |
| Network | **Jupiter** | Fast enough that separating the two is viable at all. |
| Format | **Capacitor** | Proprietary **columnar** format. This is why `SELECT *` costs money. |

So the interesting question is never "how big is my warehouse" but **"how much of it does this
query have to read?"** — because on-demand pricing bills exactly that.

## 2. Components

| component | what it is |
|---|---|
| **Dataset** | A container with a **location**. **IAM attaches here** — the usual unit of sharing. |
| **Table** | Native, external, view, materialized view, snapshot, or clone. |
| **Partition** | A physical division, usually by date. **Max 4,000 per table.** |
| **Clustering** | A *sort order* within partitions, **up to 4 columns**. Not a partition. |
| **Slot** | A unit of compute. On-demand gets them implicitly; capacity reserves them. |
| **Block** | The physical read unit, carrying per-column min/max — what clustering prunes. |
| **Storage Write API** | The modern unified ingest path; replaces legacy `insertAll`. |
| **`INFORMATION_SCHEMA`** | Metadata as queryable views — jobs, storage, reservations. |
| **Time travel** | Query the table as it was, **2–7 days** back. |

## 3. Where the data lives — native, external, BigLake, Omni

| | data sits in | security | use when |
|---|---|---|---|
| **Native** | BigQuery (Capacitor) | full — column, row, masking | the default |
| **External table** | GCS / Drive (CSV, JSON, Avro, Parquet, ORC) | **no fine-grained security, no caching** | quick exploration of lake files |
| **BigLake** | GCS / **S3 / Azure Blob** | **full BigQuery security on external files** — row + column via policy tags | you must leave data in the lake but still govern it |
| **Omni** | **AWS / Azure**, queried in place | — | data cannot move for compliance or egress cost; the query runs in the remote region, **only results return** |

**BigLake is the modern evolution of external tables**, and the distinction is heavily tested: an
external table cannot carry policy tags; a BigLake table can.

## 4. Performance and cost — partitioning vs clustering

| | partitioning | clustering |
|---|---|---|
| mechanism | physical segments | **sorted** within a partition |
| types | DATE/TIMESTAMP/DATETIME, or integer range | strings, numerics, dates, booleans |
| limit | **4,000 partitions** | **4 columns**, unlimited values |
| cardinality | **low** — usually a date | **high** — ids, stations |
| primarily | **reduces cost** | **improves speed** |
| guarantees | pruning is exact | pruning is best-effort |

Use clustering on columns that appear in `JOIN`, `WHERE`, or `GROUP BY`.

**Measured** (`partition_pruning.py` — a *labelled Parquet simulation*, see part 10):

| lever | result |
|---|---|
| **Column projection** | **11.8×** less read for 2 columns of 10 |
| **Partition pruning** | **13.3×** less for 1 day of 14 |
| **Block pruning (clustering)** | **6.2×** clustered — and **1.0× unclustered** |

## 5. Pricing and execution model

| | on-demand | capacity (Editions) |
|---|---|---|
| bills | **per TiB scanned** (first 1 TiB/month free) | **per slot-hour** |
| capacity | shared pool, up to **2,000** concurrent slots | reserved baseline + autoscale |
| fits | unpredictable, bursty, sporadic | predictable enterprise workloads |

- **Editions**: Standard · Enterprise · Enterprise Plus.
- **Reservations** autoscale in multiples of **50 or 100** slots above a baseline.
- **Commitments**: 1-year or 3-year, steeply discounted for steady-state load.
- **Crossover measured at 702 TiB/month** — see `11_ops_cost_monitoring`.

**Interactive vs batch queries:** interactive is the default and counts against concurrency
limits. **Batch queries queue until slots are idle (up to 24 h) and do not count toward
concurrency** — the right choice for a massive daily ETL that needn't finish now.

## 6. Views — three kinds, three jobs

| | what it is | key property |
|---|---|---|
| **Logical view** | A stored query, re-run every access. | Simplifies joins. No cost saving. |
| **Authorized view** | A view granted access to the source *instead of* the users. | Shares a **slice** without granting the base table. |
| **Materialized view** | Pre-computed results **stored on disk**. | **Auto-refreshes incrementally**, and **smart tuning** silently reroutes base-table queries to it. |

**Authorized view — the exact sequence the exam asks you to order:**

1. **Create a separate dataset** — it must *not* be the source dataset, or the model doesn't work.
2. **Create the view** there, filtering the sensitive columns/rows.
3. **Authorize it** on the *source* dataset.
4. Grant analysts **Data Viewer** on the view's dataset + **Job User** to run queries.

> Source and view datasets must be in the **same location**. At scale, prefer **policy tags** for
> column-level security over hundreds of authorized views; and **authorize the whole dataset** when
> many views need the same source.

**Materialized view limits:** restricted SQL only — **no external tables, no wildcard tables, no
CDC-enabled tables**, no outer joins or analytic functions. **Smart tuning only works when the MV
is in the same dataset as the base table.** Best for high-cost queries with *small result sets*.

## 7. Getting data in

| tool | for | nuance |
|---|---|---|
| **BQ Data Transfer Service (DTS)** | scheduled loads from SaaS, GCS, databases | **cannot transfer data *out***; a job **fails after 6 hours**; also powers scheduled queries and dataset copies |
| **Datastream for BigQuery** | **near real-time CDC** from MySQL, PostgreSQL, AlloyDB, SQL Server, Oracle | uses BigQuery CDC + Storage Write API; auto-backfills, then replicates inserts/updates/deletes |
| **Storage Write API** | streaming *and* batch, one gRPC API | see below |
| **Scheduled queries** | simple recurring SQL | no dependency management — that's Dataform's job |

### Storage Write API vs the legacy streaming API

| | legacy `insertAll` | **Storage Write API** |
|---|---|---|
| semantics | best-effort dedup | **exactly-once** with stream offsets |
| cost | per row | **~50% cheaper/GB**, first **2 TiB/month free** |
| throughput | 1 GB/s | **3 GB/s** default quota |
| shape | streaming only | **unified** streaming + batch, protocol buffers |

- **Default stream** — at-least-once, immediately queryable, fewer quota limits.
- **Committed (application-created) streams** — strict exactly-once; write at offsets, then commit
  atomically.
- **The 1,500 limit:** Storage Write API appends **do not** count toward the 1,500 table-modification
  operations per day that `INSERT`/`UPDATE`/`DELETE` do.
- **Connection multiplexing** — share one gRPC connection across tables rather than creating many
  streams.
- In **Dataflow**, configure `BigQueryIO` to use it.
- Writes **directly to storage** — no GCS staging step.

## 8. Speed for dashboards — BI Engine

In-memory, sub-second, high-concurrency acceleration that any BigQuery client gets **with no code
change** (REST/JDBC/ODBC — Looker, Tableau, Power BI).

- **Intelligent caching** of hot columns/partitions, prioritising **preferred tables**.
- **Vectorized processing** — batches of data per CPU operation.
- **Dictionary and run-length encoding** in the memory layer.
- **Inherits your security model** — authorized views, row/column-level security, masking. You do
  not rebuild it in the cache.
- Combine with **partitioning** (load only recent partitions) and **materialized views** (pre-join
  and flatten for the cache).

## 9. Governance and observability

**Policy tags** are the mechanism for **column-level security** — restrict PII columns by IAM role
even for users with broad table access. **Row-level access policies** do the row equivalent.

**Analytics Hub** (BigQuery Data Sharing) shares live data across org boundaries with no copying.
The subscriber gets a **linked dataset** and **pays their own compute**.

| role | can |
|---|---|
| `analyticshub.admin` | create/update/delete exchanges, manage everyone |
| `analyticshub.publisher` | create/update/delete listings — decides what is exposed |
| `analyticshub.listingAdmin` | update/delete existing listings, manage their IAM — **cannot create** |
| `analyticshub.subscriber` | discover and subscribe, creating the linked dataset |
| `analyticshub.viewer` | browse only — **cannot subscribe or query** |

**Data clean rooms** add analysis rules — aggregation thresholds, list overlap, differential
privacy — so a partner can compute without seeing raw rows.

### `INFORMATION_SCHEMA` — the SQL audit trail

| view | answers |
|---|---|
| **`JOBS` / `JOBS_BY_PROJECT`** | most expensive SQL, who burned slots, why jobs failed |
| **`JOBS_TIMELINE`** | second-by-second slot consumption — *when* a query bottlenecked |
| **`TABLES` / `COLUMNS`** | governance — find every table with an `ssn` column |
| **`TABLE_STORAGE`** | active logical vs long-term physical vs time-travel bytes |

Scope by qualifier: `region-us.INFORMATION_SCHEMA.JOBS` (regional) vs
`my_dataset.INFORMATION_SCHEMA.TABLES` (dataset).

**`INFORMATION_SCHEMA` is retrospective SQL; Cloud Monitoring is real-time and proactive.** Key
metrics: slot utilisation (first thing to check when queries slow), query execution times,
concurrent queries, uploaded/billed bytes. Alert on a threshold — don't have an engineer writing
audit SQL to discover a pipeline failed.

## 10. Nuances — the part worth reading

**`SELECT *` is a cost bug, not a style preference.** Columnar storage means the two columns a
query needs are **11.8×** less data than all ten.

**Pruning fails silently.** Wrap a partition column in a function and BigQuery scans everything and
still returns the *right answer* — correct results, full-table bill. `require_partition_filter`
makes the mistake an error instead.

**Clustering only helps if the data is actually clustered** — measured **6.2× vs 1.0×** on identical
queries. The unclustered case shows exactly what a clustering column that isn't in your predicate
is worth: nothing.

**BigQuery is the wrong shape for point lookups.** No cheap single-row read by key at high QPS —
that is Bigtable or Firestore. Matching a product to data *size* instead of *access pattern* is the
mistake the exam keeps testing.

**Long-term storage** is 50% off after **90 days untouched** — reading does not reset the clock,
*writing* does.

## 11. When to use it — and when not

| situation | reach for |
|---|---|
| analytical scans over large tables | **BigQuery** |
| transformation expressible in SQL over data already here | **BigQuery** — do not build a Dataflow job |
| **point lookups by key, high QPS** | **Bigtable** / **Firestore** |
| transactional writes, row-level updates | **Cloud SQL / Spanner** |
| sub-second dashboard aggregates | BigQuery **+ BI Engine**, or a materialized view |
| data queried rarely, left in GCS | **external table**, or **BigLake** if it needs governing |
| data that cannot leave AWS/Azure | **Omni** |
| multi-step SQL DAG with tests and version control | **Dataform** |

## 12. What was actually run

| | |
|---|---|
| `partition_pruning.py` | ✅ **fully executed**, exit 0 — **🔬 labelled simulation** |
| `bigquery_patterns.sql` | 📝 **never submitted** — correct, sandbox-ready |
| Cloud resources | **none** — no project, no credentials, no billing |

> **The honesty line.** `partition_pruning.py` measures **Parquet**, which is columnar with
> per-block min/max — the same *mechanism* as Capacitor. So the **ratios demonstrate the mechanism
> and the absolute numbers are not BigQuery's.** This repository never presents a Parquet or DuckDB
> result as a BigQuery result.

📝 **Documented, not demonstrated:** slots and reservations, Editions, BI Engine, Omni, BigLake,
Storage Write API, DTS, Datastream, Analytics Hub, materialized-view smart tuning, time travel,
`INFORMATION_SCHEMA`.
