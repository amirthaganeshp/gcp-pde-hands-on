# Decision tables

Every "which service?" question in one place. Each row points at where the claim is demonstrated
or measured.

---

## Which storage service?

| the workload is... | reach for | because |
|---|---|---|
| analytical scans, aggregation, SQL | **BigQuery** | storage and compute separate |
| point reads/writes by key, huge scale | **Bigtable** | one sorted index, ms reads |
| documents, mobile/web, offline sync | **Firestore** | realtime listeners |
| relational, single region | **Cloud SQL** | managed MySQL/Postgres/SQL Server |
| relational + HTAP + read pools | **AlloyDB** | Postgres-compatible, columnar engine |
| relational + horizontal + global | **Spanner** | TrueTime, external consistency |
| blobs, archives, a data lake | **Cloud Storage** | four classes, lifecycle |
| a cache or session store | **Memorystore** | microseconds, and **volatile** |
| a POSIX mount for several VMs | **Filestore** | when object semantics will not do |

**The two mistakes the exam keeps testing:** BigQuery as an operational store (no cheap point
lookup), and Bigtable for analytics (no aggregation, no joins). Both are matching a product to data
*size* instead of to **access pattern**.

## Which processing service?

| if... | then |
|---|---|
| streaming, or batch and streaming from one codebase | **Dataflow** |
| existing Spark/Hadoop to move with minimal change | **Managed Spark** |
| you need HBase, Hive, Presto, init actions | **Managed Spark clusters** |
| the transformation is SQL over data already in BigQuery | **BigQuery** — build no pipeline |
| non-engineers build pipelines visually | **Data Fusion** |
| interactive cleaning and profiling first | **Dataprep** |
| a scheduled file load | **BigQuery Data Transfer Service** |

**The commonest over-engineering** is a Dataflow job that parses JSON and inserts into BigQuery. A
Pub/Sub **BigQuery subscription** does that with nothing to operate.

## Which messaging service?

| if... | then |
|---|---|
| replay by offset, consumer-owned position | **Kafka** |
| already on Kafka, want fewer operations | **Managed Service for Apache Kafka** |
| serverless, no capacity to plan | **Pub/Sub** |
| strict ordering over a large keyspace | **Kafka** partitions |
| spiky, global, unpredictable | **Pub/Sub** |
| straight into BigQuery with no pipeline | **Pub/Sub** BigQuery subscription |

> A Kafka **partition** is a replayable log with a consumer-owned offset. A Pub/Sub
> **subscription** is a server-managed queue with acks. Every other difference follows.

## Which orchestrator?

| if... | then |
|---|---|
| one scheduled query | **BigQuery scheduled query** — no orchestrator |
| a linear sequence of API calls | **Workflows** — serverless |
| dependencies across services, retries, backfill | **Cloud Composer** |
| react to an event, not a clock | **Eventarc** |
| sequence SQL *inside* BigQuery | **Dataform** |

**Composer bills continuously.** Using it for one daily query is the domain's usual
over-engineering.

## Which migration/transfer path?

| if... | then |
|---|---|
| cloud-to-GCS, ongoing or scheduled | **Storage Transfer Service** |
| on-prem to GCS over the network | **Storage Transfer Service** (agent) |
| **too big for the link** | **Transfer Appliance** — see the crossover below |
| SaaS into BigQuery on a schedule | **BigQuery Data Transfer Service** |
| a live database, minimal downtime, then stop | **Database Migration Service** |
| a live database, keep replicating | **Datastream** |

**Storage Transfer Service is for FILES; DMS and Datastream are for DATABASES.** The giveaway is
whether the source is a bucket or an engine.

## Which sharing mechanism?

| if... | then |
|---|---|
| another team, same org | authorised view / dataset IAM |
| a partner org, revocable | **Analytics Hub listing** |
| two parties joining, neither trusts | **data clean room** |
| hide columns | policy tags |
| hide rows by principal | row-level access policies |

## Which ML path?

| if... | then |
|---|---|
| data in BigQuery, standard model | **BigQuery ML** |
| forecasting many series at once | **`ARIMA_PLUS`** |
| an existing TF/ONNX model | import it, or a **remote model** |
| custom architecture or loss | **Vertex AI custom training** |
| a user is waiting, sub-second | **Vertex endpoint** — `ML.PREDICT` is batch |

---

## The crossovers — computed, not judged

| decision | crossover | measured in |
|---|---|---|
| online transfer vs appliance | **106 TB** at 1 Gbps (10.6 TB at 100 Mbps) | `07_migration_cdc` |
| BigQuery on-demand vs capacity | **702 TiB**/month (421 with a 3-yr commitment) | `11_ops_cost_monitoring` |
| logical vs physical storage billing | **2.0×** compression | `11_ops_cost_monitoring` |
| Standard vs Nearline | **1.6 reads**/month | `06_storage_decisions` |

## Debugging order

When a pipeline is wrong rather than broken, in this order — the earlier items are far more common:

1. **Is data being dropped silently?** Late data at `allowed_lateness = 0`, evicted cache keys,
   a poison message looping. None of these raise.
2. **Is the split or the window wrong?** Random splits leak the future; window size decides the
   late fraction.
3. **Is it a hot key?** Idle workers plus a slow job. Five services, one failure.
4. **Is a default doing something you did not choose?** `shuffle.partitions = 200`, `AUTO_SPLIT`,
   `all_success`.
5. **Is pruning actually happening?** A function around a partition column scans everything and
   still returns the right answer.
6. **Only then, capacity.** It is rarely the problem.
