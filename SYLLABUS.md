# Syllabus — what each section covers

Every subtopic below is drawn from one of the two source guides, not invented: the 117-page
*Success Guide: GCP Professional Data Engineer* (page numbers given as `SG pp.`) and the
*Ultimate Comprehensive Edition*, which is organised by the official exam domains (`§` references).

**Legend:** ✅ runs locally · 🔬 local simulation, labelled as such · 📝 write-only, never submitted

---

## Layout — one folder, one README, one set of Python examples per service

**Every service gets its own folder and its own README.** A section README covers the decision
between services; a service README covers the service itself.

```
<NN_section>/
  README.md                 the section: the decision between these services
  <NN_service>/
      README.md             THE SERVICE - contract below
      <service>_basics.py   fundamental operations, runnable, narrated
      <service>_<topic>.py  the deeper topics
      images/               figures, where one earns its place
```

### The service README contract

Six parts, in this order, every time:

| part | what it answers |
|---|---|
| **1. What it is** | One paragraph. What problem it solves, and what it replaces or competes with. |
| **2. Components** | The nouns you cannot discuss it without — topic/subscription, broker/partition/offset, row key/column family. A table. |
| **3. Fundamental operations** | The five or six things you actually do, each with **runnable Python**. |
| **4. Nuances** | The parts that bite: defaults nobody chose, limits, and the failure that raises nothing. This is the section worth writing. |
| **5. When to use it — and when not** | The decision, stated plainly, with the nearest alternative named. |
| **6. What was actually run** | Executed / simulated / write-only, per file. Never blurred. |

Python examples are **runnable where the service can run locally** and **write-only where it
cannot** — with every cloud import inside a function, so a write-only example still imports and
still runs its explanation. That pattern is carried over from the ML repo's `05_gcp`, where it let
five cloud scripts run with no credentials at all.

---

## Service index — which GCP services live in which section

The managed/open-source column is the reason most of this repo can run at all: three of the
heaviest PDE services are managed wrappers around software you can install.

| section | GCP services | actually is |
|---|---|---|
| `01_ingestion` | **Pub/Sub**, Pub/Sub Lite, **Managed Service for Apache Kafka** | Kafka is **Apache Kafka** |
| `02_beam_dataflow` | **Dataflow**, Dataflow Prime, Streaming Engine, Flex & Classic Templates | **Apache Beam** |
| `03_bigquery` | **BigQuery**, BigLake, Storage Write API, BigQuery Studio, **Dataform** | — |
| `04_managed_spark` | **Managed Service for Apache Spark** (serverless + clusters), Dataproc Metastore, **Data Fusion**, **Dataprep** | **Spark / Hadoop / Hive / Trino**; Data Fusion is **CDAP**, Dataprep is **Trifacta** |
| `05_orchestration` | **Cloud Composer**, **Workflows**, Cloud Scheduler, Eventarc | Composer is **Apache Airflow** |
| `06_storage_decisions` | **Cloud Storage**, **Bigtable**, **Firestore/Datastore**, **Spanner**, **Cloud SQL**, **AlloyDB**, Memorystore, Persistent Disk, Filestore | Memorystore is **Redis/Memcached** |
| `07_migration_cdc` | **Database Migration Service**, **Datastream**, **Storage Transfer Service**, **Transfer Appliance**, **BigQuery Data Transfer Service** | — |
| `08_sharing_and_viz` | **Analytics Hub**, **Data Clean Rooms**, **BI Engine**, **Looker**, **Looker Studio** (+ Pro), **Connected Sheets** | Looker's modelling layer is **LookML** |
| `09_ml_integration` | **BigQuery ML**, **Vertex AI** — Feature Store, Model Registry, Endpoints, Model Monitoring, Pipelines | Vertex Pipelines is **Kubeflow** |
| `10_governance_security` | **IAM**, **Organization Policies**, **Cloud KMS**, **Secret Manager**, **Sensitive Data Protection** (formerly Cloud DLP), **Dataplex**, **Knowledge Catalog**, **VPC Service Controls**, Private Google Access | — |
| `11_ops_cost_monitoring` | **Cloud Monitoring**, **Cloud Logging**, **BigQuery Reservations / Editions**, `INFORMATION_SCHEMA`, Billing budgets, Error Reporting | Monitoring is **Prometheus**-compatible |
| `12_capstone` | Pub/Sub + Dataflow + BigQuery + Composer together | — |

**~45 distinct services.** Two placement calls worth knowing about:

- **Data Fusion and Dataprep sit in `04`**, not with Beam. They are processing engines, but
  visual/no-code ones — they belong beside Managed Spark as "the other way to process", not beside the
  Beam programming model.
- **Dataform sits in `03`**, not `05`. It orchestrates SQL *inside* BigQuery; Composer orchestrates
  *services*. Putting them together implies they compete, and they do not.

---

## 00_setup ✅

- `check_environment.py` — Python, Beam, Java, emulator availability; fails loudly with the fix
- `make_data.py` — the synthetic bike-share trip stream every section uses
- Emulator control — start/stop Pub/Sub, Bigtable, Firestore, Spanner
- Why WSL and not Windows; why a separate venv

---

## 01_ingestion — *domain 2 (25%)* · SG pp. 68–72 · §2.2

### `01_pubsub/` — Pub/Sub

1. **Topics, subscriptions, messages** — the decoupling argument ✅
2. **Pull vs push vs BigQuery/GCS subscriptions** — and when a no-code direct-write beats a pipeline ✅
3. **Delivery semantics** — at-least-once as the default, **exactly-once** where supported ✅
4. **Deduplication** — publisher-assigned IDs vs your own idempotency key ✅
5. **Ordering keys** — and the throughput they cost ✅
6. **Ack deadlines and redelivery** — the most common cause of accidental duplicates ✅
7. **Dead-letter topics and retry policy** — exponential backoff, max delivery attempts ✅
8. **Schemas** — Avro/Protobuf enforcement at the topic ✅
9. **Pub/Sub vs Pub/Sub Lite vs Cloud Tasks** — the decision table 📝

### `02_kafka/` — Apache Kafka and Managed Service for Apache Kafka

Kafka is on the exam as the thing customers **arrive with**, so the questions are usually about
comparison and migration rather than about running it.

1. **Kafka's model vs Pub/Sub's** — the difference that drives every other answer:
   a Kafka **partition** is an ordered, replayable log with consumer-managed offsets;
   a Pub/Sub **subscription** is a server-managed queue with acks ✅
2. **Brokers, topics, partitions, offsets, consumer groups** ✅ *(local Kafka in KRaft mode)*
3. **Producing and consuming in Python** — `confluent-kafka` / `kafka-python` ✅
4. **Ordering and parallelism** — ordered within a partition only, which caps consumer parallelism ✅
5. **Retention and replay** — rewinding an offset, the thing Pub/Sub does differently (seek + snapshots) ✅
6. **Managed Service for Apache Kafka** — what Google runs for you and what it does not 📝
7. **Kafka Connect and Debezium** — the usual CDC on-ramp, and how it meets `07_migration_cdc` 📝
8. **Reading Kafka from Dataflow** — `KafkaIO`, and the cross-language expansion service the
   Python SDK needs for it 📝
9. **Migrating Kafka → Pub/Sub** — the Pub/Sub Group Kafka Connector, dual-write and cutover 📝
10. **The decision** — stay on Kafka, move to managed Kafka, or move to Pub/Sub 📝

---

## 02_beam_dataflow — *domain 2 (25%)* · SG pp. 73–92 · §2.4

The heaviest section, because the exam weights it heaviest.

1. **The Beam model** — PCollection, PTransform, immutability, the runner façade ✅ *(built)*
2. **Element-wise transforms** — Map, FlatMap, Filter, ParDo ✅ *(built)*
3. **Grouping and combiner lifting** — CombinePerKey vs GroupByKey, measured ✅ *(built)*
4. **Side inputs and CoGroupByKey** — small-table broadcast vs big-to-big join ✅ *(built)*
5. **Event time vs processing time** — the distinction everything downstream rests on ✅
6. **Windowing** — fixed/tumbling, sliding/hopping, **session**, global ✅
7. **Watermarks** — how the runner decides a window is complete ✅
8. **Triggers and accumulation** — early/late firing, `accumulating` vs `discarding` ✅
9. **Allowed lateness and dropped data** — measured against the 8% late events in the dataset ✅
10. **Step fusion** — why your DAG is not the execution graph 🔬
11. **Autoscaling and dynamic work rebalancing** — the straggler problem 📝
12. **Streaming Engine and Dataflow Prime** — what moves off the worker 📝
13. **Classic vs Flex templates** — and why templates exist at all 📝
14. **Cost and anti-patterns** — hot keys, unbounded global windows, per-element I/O 📝

---

## 03_bigquery — *domains 3 + 4* · SG pp. 34–67 · §3.4

Biggest topic in both guides; no official local emulator, so honesty about what ran matters most here.

1. **Architecture** — separation of storage and compute, Dremel, columnar storage 📝
2. **Partitioning** — time-unit, ingestion-time, integer-range; partition pruning 🔬 *(bytes scanned, measured)*
3. **Clustering** — block pruning, why order matters, and where it beats partitioning 🔬
4. **Pricing models** — on-demand bytes-scanned vs capacity/slots 📝
5. **Views, authorised views, materialized views** — the three and their refresh semantics 📝
6. **`SELECT *` and the cost of a column** — columnar storage made concrete 🔬
7. **Storage Write API** — vs legacy streaming inserts; stream types 📝
8. **`INFORMATION_SCHEMA`** — jobs, tables, storage; finding your own expensive queries 📝
9. **Nested and repeated fields** — `STRUCT`, `ARRAY`, `UNNEST` ✅ *(SQL semantics runnable locally)*
10. **Table types** — native, external, BigLake, snapshots, clones 📝
11. **Time travel and fail-safe** — the recovery window 📝
12. **Dataform** — SQLX, dependencies, assertions 📝

---

## 04_managed_spark — Managed Service for Apache Spark — *domain 2* · SG pp. 93–98

Managed Service for Apache Spark **is** Spark, so all of this runs locally.

1. **RDD → DataFrame → Spark SQL** — and why you stay in DataFrames ✅
2. **Transformations vs actions** — lazy evaluation, the DAG ✅
3. **The shuffle** — measured: wide vs narrow dependencies ✅
4. **Partitioning and skew** — salting a hot key ✅
5. **Broadcast joins** — the Spark equivalent of a Beam side input ✅
6. **Caching and persistence** — when it pays and when it wastes memory ✅
7. **Cluster types** — standard, single-node, **ephemeral job-scoped clusters** 📝
8. **Preemptible/spot secondary workers** — and **Enhanced Flexibility Mode (EFM)** 📝
9. **Autoscaling policies** — and why scaling down mid-shuffle hurts 📝
10. **Lift-and-shift from on-prem Hadoop** — the migration story, HDFS → GCS 📝
11. **Managed Spark vs Dataflow** — the decision, stated plainly 📝

---

## 05_orchestration — *domain 5 (18%)* · SG pp. 105–114 · §5.2, §1.7, §1.9

Composer **is** managed Airflow, so the DAGs run locally.

1. **DAGs, tasks, operators** — and the scheduler's view of time ✅
2. **`schedule` and the data interval** — the classic off-by-one-period confusion ✅
3. **Dependencies** — `>>`, task groups, fan-in/fan-out ✅
4. **Branching** — `BranchPythonOperator`, and what happens to the skipped branch ✅
5. **Trigger rules** — `all_success` through `one_failed`, `none_failed_min_one_success` ✅
6. **XCom** — passing small values, and why not to pass data ✅
7. **Sensors** — poke vs reschedule mode, and **deferrable operators** ✅
8. **Dynamic DAG generation** — one file, many DAGs ✅
9. **Retries, SLAs, alerting** ✅
10. **DAG-to-DAG** — `TriggerDagRunOperator` vs `ExternalTaskSensor` ✅
11. **Composer 2/3 autoscaling and environment sizing** 📝
12. **Composer vs Workflows vs Cloud Scheduler** — the decision 📝
13. **Dev vs prod environments** — §1.7, promoting DAGs safely 📝

---

## 06_storage_decisions — *domain 3 (20%)* · SG pp. 18–33 · §3.1–3.3

Organised as a **classification tree**, because "which storage service?" is the most common shape
of PDE question and the answer comes from placing the workload in the tree first.

```
                            ┌─ 01_object     blobs, no query engine
       by STORAGE TYPE ─────┼─ 02_block      disks attached to a VM
                            ├─ 03_file       a shared POSIX mount
                            └─ 04_in_memory  microsecond reads, volatile

       by DATA MODEL ───────┬─ 05_structured_sql   schema + joins + transactions
                            └─ 06_nosql            schema-flexible, horizontal scale
```

> A note on the naming, kept because the distinction causes real confusion: NoSQL stores are
> **semi-structured**, not unstructured. Bigtable rows and Firestore documents have plenty of
> structure — what they lack is a *fixed, enforced* schema and SQL joins. Genuinely unstructured
> data is an object in Cloud Storage.

### `01_object/` — Cloud Storage
1. Buckets, objects, prefixes — and why "folders" do not exist ✅
2. **Storage classes** — Standard → Nearline → Coldline → Archive; retrieval cost vs storage cost 🔬
3. **Lifecycle policies**, object versioning, soft delete, retention locks ✅
4. **Access control** — uniform vs fine-grained, ACLs, **managed folders**, signed URLs 📝
5. Composite objects, parallel composite uploads, resumable uploads 📝
6. Autoclass — and when it beats hand-written lifecycle rules 📝

### `02_block/` — Persistent Disk, Hyperdisk, Local SSD
1. Zonal vs regional PD; balanced / SSD / extreme 📝
2. **Hyperdisk** — provisioned IOPS and throughput as separate dials 📝
3. **Local SSD** — ephemeral, and why Spark shuffle likes it 📝
4. Snapshots vs images vs machine images 📝

### `03_file/` — Filestore, Cloud Storage FUSE
1. Filestore tiers — Basic, Zonal, Enterprise 📝
2. When a workload genuinely needs **POSIX** rather than object semantics 📝
3. **Cloud Storage FUSE** — the trap: it looks like a filesystem and is not one 📝

### `04_in_memory/` — Memorystore
1. Redis vs Memcached — the choice ✅ *(local Redis)*
2. Caching patterns — cache-aside, write-through ✅
3. Eviction policies and TTL; what "volatile" costs you ✅
4. Memorystore tiers, replicas, failover 📝

### `05_structured_sql/` — Cloud SQL, AlloyDB, Spanner
1. **Cloud SQL** — MySQL/PostgreSQL/SQL Server, read replicas, HA, vertical limits 📝
2. **AlloyDB** — HTAP, the columnar engine, read pools; when it is the answer 📝
3. **Spanner** — **TrueTime**, external consistency, horizontal scale with SQL ✅ *(emulator)*
4. Spanner **interleaved tables** and **primary-key hotspotting** — avoid monotonic keys ✅
5. Regional vs multi-region configurations, and the latency they buy 📝
6. Where **BigQuery** sits — structured and SQL, but analytical; see `03_bigquery` 📝

### `06_nosql/` — Bigtable, Firestore/Datastore
1. **Bigtable row-key design** — the single most-tested storage topic ✅ *(emulator)*
2. **Hotspotting**, field promotion, salting, reversed timestamps ✅ *(measured)*
3. Column families, cell versions, garbage-collection policies ✅
4. Bigtable filters and scans; why there are no joins ✅
5. **Firestore** — documents, collections, subcollections ✅ *(emulator)*
6. Composite indexes, query limitations, the 1-write-per-second-per-document rule ✅
7. Native mode vs Datastore mode 📝

### Cross-cutting
1. **The decision table** — every engine on one page, by access pattern 📝
2. **Terminology mapping** — row / entity / document / object across engines 📝
3. Choosing wrong: the cost of Bigtable for analytics, or BigQuery for point lookups 🔬

---

## 07_migration_cdc — *domains 1 + 2* · SG pp. 21–22, 27–30 · §2.3

1. **Homogeneous vs heterogeneous migration** — same engine vs engine change 📝
2. **Database Migration Service (DMS)** — the managed path 📝
3. **The heterogeneous lifecycle** — assess & convert, apply schema, replicate (CDC), promote & cutover 📝
4. **Datastream** — serverless CDC, source → GCS/BigQuery 📝
5. **CDC patterns** — append-only log vs merged current state ✅ *(the merge logic is runnable)*
6. **Storage Transfer Service** — online bulk, cloud-to-cloud 📝
7. **Transfer Appliance** — the offline path, and the bandwidth maths that decides it 🔬
8. **BigQuery Data Transfer Service** — scheduled SaaS ingests 📝
9. **The decision matrix** — volume × bandwidth × downtime tolerance 🔬 *(computed, not asserted)*

---

## 08_sharing_and_viz — *domain 4 (15%)* · SG pp. 40, 45, 65–66 · §4.1, §4.3

1. **Analytics Hub** — publisher/subscriber, listings, linked datasets 📝
2. **Data clean rooms** — aggregation thresholds, joining without exposing rows 📝
3. **Authorised views and datasets** — sharing a slice, not the table 📝
4. **Row-level and column-level security** — policy tags, masked reader 📝
5. **BI Engine** — the in-memory acceleration layer and its limits 📝
6. **Preparing data *for* visualisation** — pre-aggregation, materialized views, the wide-table pattern 🔬
7. **Looker vs Looker Studio vs Looker Studio Pro** — semantic layer vs ad hoc 📝
8. **Connected Sheets** — when the business simply will not leave the spreadsheet 📝
9. **Dashboard performance** — why a slow dashboard is usually a modelling problem 🔬

---

## 09_ml_integration — *domain 4* · SG pp. 56–62 · §4.2

**Deliberately thin.** The `machine-learning` repo covers this properly; this section cross-links
rather than duplicates, and says so.

1. **BigQuery ML** — the model types PDE actually tests 📝
2. **`CREATE MODEL` and `DATA_SPLIT_METHOD`** — including the `AUTO_SPLIT` rule 📝
3. **`ML.PREDICT`, `ML.EVALUATE`** — batch scoring where the data already is 📝
4. **When BQML is right and when it is not** — the decision 📝
5. **Vertex AI, at PDE depth** — Feature Store, Model Registry, endpoints, Model Monitoring 📝
6. **Training/serving skew** — the failure a data engineer causes 🔗 *(see `machine-learning/01_foundations/05_data_leakage`)*

---

## 10_governance_security — *domain 1 (22%)* · SG pp. 1–17 · §1.1–1.6

1. **IAM** — principals, roles, policies; **inheritance is additive and cannot be revoked lower down** 📝
2. **Basic vs predefined vs custom roles**; least privilege in practice 📝
3. **Service accounts** — attach, don't download keys; impersonation 📝
4. **Organization policies** — constraints, and how they differ from IAM 📝
5. **Encryption tiers** — default (GMEK), **CMEK**, CSEK; the service-agent permission trap 📝
6. **Cloud KMS vs Secret Manager** — keys for data, secrets for strings 📝
7. **DLP / Sensitive Data Protection** — infoTypes, likelihood thresholds 📝
8. **De-identification techniques** — masking, redaction, secure-hash pseudonymisation, **FPE**, generalisation/bucketing, date shifting ✅ *(the transforms are runnable locally)*
9. **Policy tags and taxonomies** — fine-grained reader vs masked reader 📝
10. **Dataplex** — data mesh, lakes/zones/assets, discovery, data quality 📝
11. **Data Catalog → Dataplex Universal Catalog → **Knowledge Catalog**** — the rename, and what moved 📝
12. **Data residency and sovereignty** — `constraints/compute.resourceLocations` 📝
13. **VPC Service Controls and Private Google Access** — §2.1's networking 📝

---

## 11_ops_cost_monitoring — *domain 5 (18%)* · SG pp. 36, 48–50, 115–117 · §5.1, §5.3, §5.4

1. **BigQuery Editions and reservations** — Standard/Enterprise/Enterprise Plus, autoscaling slots 📝
2. **On-demand vs capacity pricing** — the crossover point 🔬 *(computed)*
3. **Slot contention and query queuing** 📝
4. **Cost controls** — custom quotas, maximum bytes billed, required partition filter 📝
5. **Storage billing** — active vs long-term, physical vs logical 🔬
6. **Finding the expensive query** — `INFORMATION_SCHEMA.JOBS` patterns 📝
7. **Cloud Monitoring metric types** — gauge, **counter**, **distribution** 📝
8. **Alerting policies** — thresholds, duration windows, and why a naive threshold pages at 3 a.m. 🔬
9. **Notification channels and incident flow** 📝
10. **Log sinks and metric export** — the retention default and long-term storage 📝
11. **Dataflow and Managed Spark cost levers** — machine type, spot, shuffle location 📝

---

## 12_capstone — *all domains* · §7

One pipeline, end to end, wired from the parts above.

1. **The architecture** — Pub/Sub → Dataflow (windowed) → BigQuery (partitioned + clustered) → a
   reporting view, orchestrated by Airflow ✅
2. **Where each earlier section shows up** — an explicit map
3. **The failure modes** — late data, a poison message, a schema change, a hot key ✅
4. **What it would cost on GCP** — priced, not hand-waved 🔬
5. **What changes to make it production** — the honest list of what a demo omits 📝

---

## 99_reference

- `EXAM_DOMAIN_MAP.md` — domain → repo section → guide pages, both directions
- `CLI_REFERENCE.md` — the `gcloud` / `bq` / `gsutil` commands worth knowing (§6)
- `DECISIONS.md` — every decision table in one place
- `FINDINGS.md` — measured results, contradictions first
- `GLOSSARY.md` — terms, each pointing at where it is demonstrated
