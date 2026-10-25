# Capstone — one pipeline, and the four ways it breaks

> **All domains** · Ultimate §7 *Unified Data Engineering Pipeline Architecture*
> **Runtime:** ~6 s · **Needs:** `apache-beam`, `google-cloud-pubsub`, the Pub/Sub emulator, Java

```bash
python 12_capstone/pipeline_end_to_end.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

---

## 1. What it is

```
Pub/Sub  ->  Beam  ->  outputs/capstone/agg
(emulator)   (windowed by event time)   (station x hour aggregates)
```

**The sink is one pipe-delimited text file**, `outputs/capstone/agg`, one line per
`window_start|station|sum_minutes` — not Parquet, not partitioned, not a BigQuery layout. It
stands in for the warehouse table; partitioning and clustering are shown in `03_bigquery`.

**Nothing here is new.** Every piece was built in an earlier section. The capstone exists because
the exam's hardest questions — and production — are about the **seams**, not about any single
service.

| concern | section |
|---|---|
| Pub/Sub ingest, DLQ, at-least-once | `01_ingestion` |
| windowing by event time, late data | `02_beam_dataflow` |
| partitioned + clustered layout — *not reproduced here*; the sink is one flat file | `03_bigquery` |
| an idempotent MERGE on a business key | `07_migration_cdc` |
| a reporting aggregate, not raw rows | `08_sharing_and_viz` |
| orchestration, branching, trigger rules | `05_orchestration` |
| alert on freshness, not row count | `11_ops_cost_monitoring` |

## 2. The full reference architecture

The guide's unified flow, in five stages. The demo implements the shaded middle; the rest is
documented in the sections named.

```
1. INGESTION          2. NETWORK +        3. PROCESSING      4. STORAGE +        5. ANALYTICS
                         DE-IDENTIFY                            WAREHOUSE           + SERVING

on-prem DBs  --[Private Service Connect]-->  Managed Spark  -->  Cloud Storage  --+
(Oracle/MySQL)                               (ephemeral batch)   (data lake)      |
                                                                                  v
mobile / IoT --[Private Google Access]-->  Pub/Sub  -->  Dataflow  -->  BigQuery  --> Looker /
                                              |          (Beam ETL)    (warehouse)     Looker Studio
                                              v                             |
                                   Sensitive Data Protection                v
                                   (IN-FLIGHT redaction)              Vertex AI
                                                                   (embeddings, RAG)
```

| stage | the decision it encodes | covered in |
|---|---|---|
| **1. Ingestion** | a *log* (Kafka) or a *queue* (Pub/Sub); CDC for databases | [`01_ingestion`](../01_ingestion/), [`07_migration_cdc`](../07_migration_cdc/) |
| **2. Network + de-identify** | PSC/PGA so nothing traverses the internet; **redact in flight, before landing** | [`10_governance_security`](../10_governance_security/) |
| **3. Processing** | Dataflow for new/streaming, Managed Spark for lift-and-shift; **ephemeral** clusters | [`02_beam_dataflow`](../02_beam_dataflow/), [`04_managed_spark`](../04_managed_spark/) |
| **4. Storage** | lake in GCS, warehouse in BigQuery, partitioned and clustered | [`06_storage_decisions`](../06_storage_decisions/), [`03_bigquery`](../03_bigquery/) |
| **5. Analytics + serving** | BI Engine and MVs for speed; BQML in place vs Vertex for the rest | [`08_sharing_and_viz`](../08_sharing_and_viz/), [`09_ml_integration`](../09_ml_integration/) |

**Two properties of this diagram are the actual exam content**, and both are easy to miss:

- **De-identification sits *before* the warehouse, not after.** Redacting once the raw PII has
  landed means the unprotected copy already exists.
- **The lake and the warehouse both exist, and neither replaces the other.** GCS holds raw and
  archival data cheaply; BigQuery holds the modelled, queryable form. BigLake is how one set of
  files gets governed like the other.

## 3. What it does

| measured | result |
|---|---|
| messages published and drained from Pub/Sub | **3,000** |
| aggregate rows out | **1,462** |
| hourly windows | 306 |
| stations | 8 |

Output is **station × hour aggregates, not raw trips** — the reporting table is a *derived*
artefact. The raw stream stays the source of truth, which is what makes a bug in the aggregation
recoverable rather than fatal.

## 4. The four failures

A demo that only shows the happy path teaches that the happy path is the whole path. These are run,
not described.

**A poison message.** One unparseable payload published alongside a valid one: **1 parsed, 1
failed**. Without a dead-letter topic it is redelivered *forever* — never acked, burning quota and
filling logs while the real problem stays invisible. In Beam this is a side output: route failures
to a second PCollection rather than letting one bad record kill the bundle.

**Late data.** **40 of 3,000 (1.3%)** arrived after their window closed. At `allowed_lateness = 0`
they are dropped **silently** — no error, no log, no metric. The hourly total is simply wrong and
nothing says so. Window size decides how much this is: the same stream in one-minute windows loses
**23.9%** and in one-hour windows **1.3%**.

**A schema change.** Two changes arrived together and they are not equally dangerous:

| change | result |
|---|---|
| a **new field** appeared | **harmless** — JSON readers ignore what they do not ask for |
| an existing field became **nullable** | **broke the pipeline** — the code assumed a float |

Additive change is the only safe kind. A **schema on the topic** (Avro or Protobuf) turns this into
a publish-time rejection rather than a 3 a.m. consumer crash.

**A hot key.** Mild in this dataset (1.1×) and deliberately so — the point is that **the same
failure appears in five services already built here:**

| service | how it shows up | measured |
|---|---|---|
| Pub/Sub | ordering key serialises to one subscriber | — |
| Kafka | one partition, one consumer | 3 of 5 consumers idle |
| Beam | one key, one worker, a straggler | — |
| Spark | skewed partition | **34.5×** imbalance |
| Bigtable | one tablet, one node | **1 of 8** tablets |

Five products, one failure mode. Recognise it by **shape** — a cluster idle while the job is slow —
rather than memorising five fixes, because the fix is always the same: spread the key, or accept
the serialisation.

## 5. What this demo omits — stated, not hidden

| missing | why it matters |
|---|---|
| **Beam reads a bounded snapshot** | a real job reads an unbounded subscription; watermarks are inferred, not replayed |
| the warehouse is one local text file | no partitions, no clustering, no slots, no billed pruning, no 10 MB minimum |
| no orchestration running | the DAG in `05_orchestration` would trigger this |
| no IAM at all | every service runs as you, with no boundary |
| no retry or idempotency | re-running appends; production needs the `MERGE` |
| no monitoring | nothing here would page anyone |
| one machine | no shuffle across workers, so no network cost |

**The bounded-vs-streaming boundary is the important one.** Reading a drained snapshot means the
watermark comes from the data rather than from a live source — so the late-data figure in §3 is
**computed from timestamps rather than observed from a runner**. That is consistent with the
negative result already recorded in [`02_beam_dataflow`](../02_beam_dataflow/), where late-pane
firing did not reproduce on any local runner.

## 6. What was actually run

| | |
|---|---|
| `pipeline_end_to_end.py` | ✅ **fully executed**, exit 0 |
| Pub/Sub | real emulator, started and stopped by the script |
| Beam | 2.76.0, `DirectRunner` → Prism |
| Cloud resources | **none** |

> The services are the easy part. The seams are where the exam — and production — actually lives.
