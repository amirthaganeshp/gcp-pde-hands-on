# Apache Kafka (and Managed Service for Apache Kafka)

> **Domain 2 — Ingesting and Processing the Data (25%)** · Success Guide pp. 68–72 · Ultimate §2.2
> **Runtime:** ~65 s · **Needs:** `confluent-kafka`, Java 17+, Kafka **already unpacked** in `~/kafka` — the script does **not** download it; if it is missing it exits with the `curl` commands to fetch the current release

```bash
python 01_ingestion/02_kafka/kafka_basics.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

Kafka is on the PDE exam mostly as **the thing customers arrive with**. The questions are about
comparison and migration, not about operating a cluster — so this section is built around the one
distinction that decides every such question.

---

## 1. What it is

Kafka is a **distributed, replayable commit log**. A topic is an append-only sequence split into
*partitions*; consumers track their own position (an *offset*) and can move it backwards. The
broker keeps messages for a configured retention period **whether or not anyone read them**.

Pub/Sub is a **queue with server-managed acknowledgement**. Once every subscription has acked a
message, it is gone.

> **A Kafka partition is a replayable log with a consumer-owned offset.**
> **A Pub/Sub subscription is a server-managed queue with acks.**
>
> Nearly every other difference is a consequence of that one.

| consequence | Kafka | Pub/Sub |
|---|---|---|
| replay | rewind an offset — free | `seek` + a snapshot taken **in advance** |
| ordering | total, per partition | per ordering key |
| consumer parallelism | **capped by partition count** | uncapped |
| retention | time or size | until every subscription acks |
| operations | a cluster you size | no dials |

## 2. Components

| component | what it is |
|---|---|
| **Broker** | A server holding partitions. A cluster is several. |
| **Topic** | A named log, split into partitions. |
| **Partition** | **The unit of ordering, parallelism, storage and replication — all at once.** Pub/Sub has no equivalent. |
| **Offset** | A consumer's position in a partition. Owned by the consumer, not the broker. |
| **Consumer group** | A set of consumers sharing a subscription. Partitions are divided among them. |
| **Key** | Hashed to pick a partition. Same key → same partition → ordered. |
| **Replication factor** | Copies per partition. 1 here; ≥3 in production. |
| **KRaft** | The built-in consensus layer. **Modern Kafka has no ZooKeeper** — any tutorial that starts one is out of date. |

## 3. Fundamental operations

All measured against a local single-node broker the script starts and stops itself.

| # | operation | measured |
|---|---|---|
| 2 | create a topic with 3 partitions | `[0, 1, 2]` |
| 3 | produce 45 messages across 9 keys | each key → exactly one partition |
| 4 | run consumer groups of 3 and 5 | 3 get work; **at 5, two sit idle** |
| 5 | read from offset 0, rewind, read again | 45 then 45, identical |
| 6 | read one partition in order | ordered ✅ |

```python
# The key decides the partition. Same key, same partition, ordered.
producer.produce("trips", key=b"ST01", value=b'{"trip_id":"T0001"}')

# The consumer owns its position - this is the replay.
consumer.assign([TopicPartition("trips", 0, 0)])
consumer.seek(TopicPartition("trips", 0, 0))
```

## 4. Durability, retention and delivery

### How long the log keeps data

| policy | behaviour | for |
|---|---|---|
| **Time / size retention** | delete segments older than `retention.ms` or beyond `retention.bytes` | event streams — the default |
| **Log compaction** | keep **the latest value per key**, forever | a changelog you can replay into current state — CDC, config, materialised views |

> **Compaction makes a topic behave like a table.** Replay it from offset 0 and you get one row per
> key: the same idea as the CDC merge in
> [`07_migration_cdc`](../../07_migration_cdc/01_datastream/), expressed as a retention setting.
> **Pub/Sub has no equivalent** — its retention is time-bounded only.

### Durability on write

| setting | meaning | risk |
|---|---|---|
| `acks=0` | fire and forget | data loss on any failure |
| `acks=1` | the **leader** wrote it | loss if the leader dies before replicas catch up |
| **`acks=all`** | every **in-sync replica** wrote it | the durable choice |

**ISR (in-sync replicas)** is the set of replicas currently caught up with the leader. With
`acks=all` plus `min.insync.replicas=2` on RF=3, a write needs two copies — so one broker can die
without loss *and* without blocking writes. **Replication factor alone guarantees nothing** if
`acks` lets the producer move on early.

### Delivery semantics

| | how |
|---|---|
| **at-most-once** | commit the offset *before* processing |
| **at-least-once** (default) | process, then commit — a crash in between reprocesses |
| **exactly-once (EOS)** | **idempotent producer** (dedupes retries) + **transactions** spanning the write and the offset commit |

> Kafka's exactly-once is **within Kafka** — a read-process-write whose output topic and offset
> commit are one atomic transaction. It says nothing about an external sink. Writing to BigQuery
> still needs an idempotent `MERGE`, exactly as everywhere else in this repo.

### The ecosystem the exam expects you to recognise

| | what it is |
|---|---|
| **Kafka Connect** | Pluggable source/sink connectors — the "don't write a consumer" path. |
| **Schema Registry** | Central Avro/Protobuf schemas with **compatibility enforcement**, so a producer cannot break consumers. Pub/Sub's topic schemas are the managed analogue. |
| **Kafka Streams / ksqlDB** | Stream processing inside Kafka — the thing Dataflow replaces on GCP. |

## 5. Nuances — the part worth reading

**The partition count is a ceiling on consumers, and it is measured here.** A partition is assigned
to **at most one consumer in a group**:

```
group of 3 over 3 partitions : assigned {0:1, 1:1, 2:1}  -> 3 of 3 given work
group of 5 over 3 partitions : assigned {0:1, 1:1, 4:1}  -> 3 of 5, TWO IDLE
```

Consumers past the partition count are not sharing load — they are spare capacity waiting for a
rebalance. Scaling out a consumer group without adding partitions does nothing.

**Partition count is the decision you cannot undo.** You can add partitions, never remove them —
and adding them **breaks the existing key→partition mapping**, so a key starts landing somewhere
new and its ordering guarantee is broken across the change.

**The hash spreads keys evenly, not volume.** Measured with 9 keys over 3 partitions:

```
messages per partition: {0: 20, 1: 5, 2: 20}      spread 5 to 20 (4.0x)
```

Same total, 4× imbalance, from nothing but which key hashed where. With fewer keys a partition can
receive **nothing at all**. This is the same failure as a Pub/Sub hot ordering key or a Bigtable hot
row key, and it is why "add partitions" does not fix a skewed workload.

**Assignment and receipt are different things.** A consumer can hold a partition and still get
nothing, because that partition is empty. Conflating them is a real trap — an earlier version of
this script did, reported `0` received, and its summary still claimed "all active". Both numbers
are now printed separately.

**The log persists, so a re-run is not a clean run.** Running this file twice against the same
topic appended to it: 45 produced, **75 read**, and the ordering check went `False` because two
runs' ids interleaved. The script now deletes and recreates the topic first — and that step exists
*because Kafka retains*, which is the distinction in section 1 showing up as an operational detail.
Pub/Sub would not behave this way.

**Rebalances take real time.** A group's first join must wait for the coordinator to assign
partitions. An impatient poll loop reports a false zero — which is exactly what happened before the
timeout here was raised to 30 s.

**Ordering and parallelism are exchanged, always.** A total order means one partition, which means
one consumer, which means no parallelism. Identical trade to a Pub/Sub ordering key, reached from
the other direction.

## 6. When to use it — and when not

| situation | reach for |
|---|---|
| replay by offset, consumer-owned position | **Kafka** |
| already on Kafka, want less operational load | **Managed Service for Apache Kafka** |
| serverless, no capacity to plan | **Pub/Sub** |
| strict ordering over a large keyspace | **Kafka** partitions |
| unpredictable, spiky, global traffic | **Pub/Sub** |
| sub-10 ms in-region latency, willing to run brokers | **Kafka** |
| straight into BigQuery with no pipeline | **Pub/Sub** BigQuery subscription |

**Managed Service for Apache Kafka is usually the right exam answer** when a question says the
customer has Kafka and wants to reduce operations **without a rewrite**. It is real Kafka — clients,
Kafka Connect and offsets all keep working. Google runs the brokers; you still choose partition
counts and still think about consumer groups.

**Migrating to Pub/Sub is a genuine rewrite of consumer semantics** — offsets become acks, replay
becomes seek-plus-snapshot. The **Pub/Sub Group Kafka Connector** bridges the two during a
dual-write cutover; it does not make them equivalent.

> The question is never "which is better". It is **"does this workload need a replayable log, or a
> queue?"**

## 7. What was actually run

| | |
|---|---|
| `kafka_basics.py` | ✅ **fully executed**, exit 0 |
| Broker | **Apache Kafka 4.3.1**, single node, **KRaft** — started and stopped by the script |
| Client | `confluent-kafka` (librdkafka **2.15.1**) |
| Java | OpenJDK **21.0.12.1** — KRaft needs 17+ |
| Cloud resources | **none** |

Managed Kafka specifics (Google-run brokers, VPC peering, IAM) are 📝 **write-only** — there is no
emulator, and the exam tests the decision rather than the console.

**One environment note:** `downloads.apache.org` carries only *current* releases — older ones move
to `archive.apache.org`. A hardcoded version list fails with "no release reachable" and looks like a
network problem. So the fetch commands the script prints when `~/kafka` is missing discover the latest
version from the directory listing instead; that found 4.3.1 where a hardcoded list had topped out
at 4.1.0.
