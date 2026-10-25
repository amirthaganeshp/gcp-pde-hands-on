# Managed Service for Apache Spark (formerly Dataproc)

> **Domain 2 — Ingesting and Processing (25%)** · Success Guide §11.5.2 · Ultimate §2.4
> **Runtime:** ~15 s · **Needs:** `pyspark` + Java 21 — no cloud, no cluster

```bash
python 04_managed_spark/01_spark/spark_basics.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

> **The name changed; the CLI did not.** The product is now *Managed Service for Apache Spark*,
> but every command is still `gcloud dataproc …`. See
> [`99_reference/SERVICE_NAMES.md`](../../99_reference/SERVICE_NAMES.md).

---

## 1. What it is

Managed Hadoop/Spark on GCE. On the exam it is almost exclusively **the target for lift-and-shift
migrations** of existing on-premises big data workloads — Spark, Hadoop, Hive, Flink, Presto, Pig.

**Dataproc *is* Apache Spark**, which is why this section runs locally: the same PySpark code,
the same plans, the same shuffle.

| model | you get | choose when |
|---|---|---|
| **Serverless** | submit a batch, no cluster to size | the job is the unit of work — most new work |
| **Clusters (on GCE)** | long-lived, tunable, full ecosystem | you need HBase/Hive/Presto, init actions, persistent HDFS |
| **On GKE** | Spark alongside microservices | the org standardised on Kubernetes |

## 2. Cluster anatomy

| node | runs | holds data? |
|---|---|---|
| **Master** | YARN Resource Manager, HDFS NameNode | coordinates; tracks where data lives |
| **Primary workers** | compute **and** HDFS storage | **yes** — must be standard VMs |
| **Secondary workers** | **compute only** | **no** — almost always **Spot/Preemptible**, up to ~80% cheaper |

**Master nodes cannot be Spot.** Secondary workers can, precisely because they hold no HDFS data
— losing one costs compute, not data.

## 3. The two rules that define correct use

**1. Decouple storage.** Permanent data belongs in **Cloud Storage**, not HDFS. The native GCS
connector lets Spark read `gs://` as if it were local. HDFS on a cluster you intend to delete is a
data-loss design.

**2. Make clusters ephemeral.** Because the data is safe in GCS, spin a cluster up **for one job**
and delete it when the job ends. A 24/7 Hadoop cluster is the on-prem habit the exam is testing
you to break — persistent clusters are for long-running multi-user interactive notebook work only.

## 4. Spark internals — what the illustration measures

| component | what it is |
|---|---|
| **Driver** | Builds the plan and schedules tasks. |
| **Executor** | Runs tasks, holds cached data. |
| **Partition** | The unit of parallelism. **One partition = one task = one core.** |
| **Narrow transformation** | Needs only the local partition — `map`, `filter`, `withColumn`. |
| **Wide transformation** | Needs rows from everywhere — `groupBy`, `join`, `distinct`. **Causes a shuffle.** |
| **Action** | `count`, `collect`, `write` — the only thing that makes anything run. |
| **AQE** | Adaptive Query Execution: re-plans mid-job using real statistics. |

**Measured:**

| | result |
|---|---|
| chaining 3 transformations | **143 ms** (schema/Python only — nothing ran) |
| the `count()` action on them | **714 ms** — this is where the work happened |
| partitions after a **narrow** step | 2 → **2** (unchanged) |
| partitions after a **wide** step | 2 → **200** (`spark.sql.shuffle.partitions`) |
| groups actually produced | **8** |
| one hot key, 8 partitions | **34.5×** imbalance |
| after salting | **10.8×** — *helps, does not solve* |
| shuffle join → real shuffle? | **True** |
| broadcast join → real shuffle? | **False** |

**`spark.sql.shuffle.partitions = 200` is a default nobody chose.** Eight groups became 200
partitions, 192 of them empty. On a small job it is pure overhead; on a big one, far too few.

## 5. Optimisation and autoscaling

| lever | what it does | the catch |
|---|---|---|
| **Init actions** | Bash scripts from GCS run on **every node** at creation. | **Slows every boot** — packages download on each start. |
| **Custom images** | Pre-baked Compute Engine image with your dependencies. | The optimised path: boots instantly. |
| **Autoscaling** | Scales on **YARN memory** metrics. | Removing a busy worker **crashes the job** unless… |
| **Graceful decommissioning** | **Must be explicitly enabled.** YARN waits for tasks to finish and shuffles intermediate data off the node first. | Without it, autoscaling and Spot preemption both kill jobs. |
| **EFM** (Enhanced Flexibility Mode) | Separates shuffle data from compute. | The companion fix for Spot-heavy clusters. |

## 6. Troubleshooting

| symptom | cause | fix |
|---|---|---|
| YARN jobs stuck in **ACCEPTED**, never running | cluster has no free RAM/CPU and the autoscaler is at its max | raise max primary/secondary workers, or use a higher-memory machine type |
| **HDFS quota exceeded / disk full** | writing permanent output or big shuffles to local HDFS | write output to `gs://`; add local SSD for shuffle |
| Job dies when **Spot VMs are reclaimed** | in-flight executors killed, shuffle data lost | **graceful decommissioning + EFM** |
| Nodes can't talk; cluster creation times out | internal networking blocked | VPC firewall must allow **internal ingress on all TCP/UDP** for the Dataproc network tags |

## 7. Nuances — the part worth reading

**Lazy evaluation is why timings mislead.** Three chained transformations returned in 143 ms
because **nothing ran** — only the action forced the 714 ms of real work. Any benchmark that times
transformations rather than actions is measuring Python.

**Salting helps; it does not solve.** 34.5× → **10.8×**, not → 1×. Kept as an honest negative
rather than tuned until it looked clean.

**Checking for a shuffle by substring is a trap.** A naive `"Exchange" in plan` is **wrong**,
because a broadcast plan contains `BroadcastExchange` and matches it. Test for
`hashpartitioning` / `rangepartitioning` instead — this repo got that wrong once.

**A broadcast join is the same idea as a Beam side input**, with the same hard limit: the small
side must fit in executor memory.

## 8. Dataproc vs Dataflow

| choose **Managed Spark** when | choose **Dataflow** when |
|---|---|
| existing Spark/Hadoop code to move | building new pipelines from scratch |
| you rely on the OSS ecosystem (Spark MLlib, Hive) | you need real streaming — watermarks, windows |
| cross-cloud portability matters | you want fully serverless, zero-ops |
| you need HBase/Presto/init actions | autoscaling per stage |

## 9. What was actually run

| | |
|---|---|
| `spark_basics.py` | ✅ **fully executed** on local PySpark, exit 0 |
| Spark | real Apache Spark — the same engine the service runs |
| Cloud resources | **none** — no cluster, no project, no billing |

📝 **Documented, not demonstrated:** cluster provisioning, YARN/HDFS, secondary Spot workers,
autoscaling policies, graceful decommissioning, EFM, init actions, custom images, Serverless
batches, Dataproc on GKE.
