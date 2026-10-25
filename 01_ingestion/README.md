# Ingestion — getting data in

> **Domain 2 — Ingesting and Processing the Data (25%)**, the heaviest domain
> Success Guide pp. 68–72, §11.1 · Ultimate §2.1–2.2

| service | covers | state |
|---|---|---|
| [`01_pubsub/`](01_pubsub/) | topics vs subscriptions, pull vs push, the lease lifecycle, exactly-once, DLQ, seek | ✅ **built** (emulator) |
| [`02_kafka/`](02_kafka/) | partitions as the unit of ordering and parallelism, consumer groups, offsets, replay | ✅ **built** (real broker) |

**Related, documented elsewhere:** CDC ingestion is [`../07_migration_cdc/01_datastream/`](../07_migration_cdc/01_datastream/);
scheduled and bulk loads are [`../07_migration_cdc/02_transfer/`](../07_migration_cdc/02_transfer/);
the Storage Write API is in [`../03_bigquery/01_bigquery/`](../03_bigquery/01_bigquery/).

---

## The one sentence this section is built around

> A Kafka **partition** is a replayable log with a **consumer-owned offset**.
> A Pub/Sub **subscription** is a server-managed queue with **acks**.
> **Every other difference follows from that.**

| | **Pub/Sub** | **Kafka** |
|---|---|---|
| architecture | managed, serverless, global. **No partitions, no brokers, no shards.** | a cluster you run (KRaft, or ZooKeeper historically) |
| ops | zero — scales with traffic | capacity planning, partition counts, rebalancing |
| position | server tracks acks | **the consumer owns its offset** |
| replay | seek to a timestamp or snapshot | rewind the offset, arbitrarily |
| ordering | ordering keys, **at a throughput cost** | **free within a partition** |
| scaling consumers | add clients to a subscription | **capped by partition count** |

## What each one measured

**Pub/Sub — at-least-once is not an error condition.** Pull a message, decline to ack it, wait out
the 10-second deadline, pull again: **the same message comes back, with nothing having failed.**
That single observation is why every downstream handler in this repo is idempotent.

**Kafka — the partition count is a ceiling on consumers, and it was measured:**

```
group of 3 over 3 partitions : assigned {0:1, 1:1, 2:1}  -> 3 of 3 given work
group of 5 over 3 partitions : assigned {0:1, 1:1, 4:1}  -> 3 of 5, TWO IDLE
```

**And keys spread evenly while volume does not.** Nine keys over three partitions gave
`{0: 20, 1: 5, 2: 20}` — a 4.0× imbalance from hashing alone. That is the same hot-key shape that
appears in Spark, Bigtable, Beam and Dataflow; see
[`99_reference/FINDINGS.md`](../99_reference/FINDINGS.md) §1.

## Choosing

| the requirement | reach for |
|---|---|
| native GCP async messaging, spiky or global traffic | **Pub/Sub** |
| fan-out to several independent consumers | **Pub/Sub** — one subscription each |
| straight into BigQuery with no pipeline | **Pub/Sub BigQuery subscription** |
| strict ordering over a large key space | **Kafka** partitions |
| replay from an arbitrary offset | **Kafka** |
| cross-cloud portability, or lifting an existing cluster | **Kafka** — or **Managed Service for Apache Kafka** |
| CDC from a relational database | **Datastream**, not messaging |
| scheduled file loads | **Storage Transfer / DTS**, not messaging |

> **PDE default:** choose Pub/Sub unless the question specifically requires cross-cloud
> portability or migrating an existing Kafka cluster as-is.

## What was actually run

| | |
|---|---|
| Pub/Sub | ✅ the **official emulator**, started and stopped by the script |
| Kafka | ✅ a **real broker** — Kafka 4.3.1 in **KRaft mode**, no ZooKeeper |
| Cloud resources | **none** — no project, no credentials, no billing |

> **The Kafka script deletes and recreates its topic first, deliberately.** The log persists
> between runs, so a second run would otherwise read the first run's messages. That behaviour *is*
> the lesson: a Kafka topic is a durable log, not a queue that drains.
