# Cloud Pub/Sub

> **Domain 2 — Ingesting and Processing the Data (25%)** · Success Guide pp. 68–72 · Ultimate §2.2
> **Runtime:** ~15 s · **Needs:** the Pub/Sub emulator (the script starts and stops it) + Java

```bash
python 01_ingestion/01_pubsub/pubsub_basics.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

---

## 1. What it is

A **fully managed, global, serverless** asynchronous messaging service that decouples publishers
from subscribers. It carries >500 M messages/sec across Google's own services.

**It has no clusters, no brokers, no partitions and no shards.** You set quotas, publish, and
consume. That single sentence is most of the difference from Kafka, and everything else follows
from it.

## 2. Components

| component | what it is |
|---|---|
| **Topic** | A named resource publishers send to. |
| **Subscription** | An independent backlog attached to a topic. **This is where messages queue.** |
| **Message** | `data` (bytes) + `attributes` (string map) + a server-assigned `message_id`. |
| **Ack / ack deadline** | Confirmation you handled it, and the window you have to say so. Default **10 s**, max **600 s**. |
| **Ordering key** | Optional. Guarantees order *within one key*, never globally. |
| **Dead-letter topic** | Where a message goes after N failed delivery attempts. |
| **Schema** | Optional Avro/Protobuf contract enforced at the topic. |
| **Snapshot / seek** | Rewind a subscription to a timestamp or snapshot to replay — or purge. |

**The one that matters most: a topic is not a queue.** Each subscription holds its own copy of
every message. Two subscriptions on one topic both receive everything — that is **fan-out**.
Competing consumers come from running several clients against *one* subscription.

> **If three systems need the same stream, create three subscriptions** — not three topics, and
> not three consumers on one subscription.

## 3. Delivery mechanisms — pull vs push

| | **pull** | **push** |
|---|---|---|
| who initiates | the subscriber calls the API | Pub/Sub sends an **HTTPS POST** to a webhook |
| flow control | **the consumer sets the rate** (backpressure) | Pub/Sub sets the rate |
| fits | high throughput, batching — Dataflow, worker pools | lightweight event-driven services that **scale to zero** (Cloud Run, Functions) |

**Pull is the default recommendation for throughput** because the consumer controls ingestion.

## 4. Delivery semantics — the part that bites

| | |
|---|---|
| **At-least-once** (default) | Every message delivered ≥ 1 time. **Duplicates are normal.** Subscribers must be idempotent. |
| **Exactly-once** | Enabled per subscription, **pull only**. Regional dedup by message ID; no redelivery after a successful ack, nor while outstanding. |

**Exactly-once is not free and not global:** it does **not span multi-regional subscriptions**, it
**adds latency**, and it demands stricter lease management.

### The lease lifecycle

| action | mechanism | effect |
|---|---|---|
| **Lease** | delivery starts the ack-deadline timer | the message is locked from other workers |
| **Extend** | client library sends `modifyAckDeadline` | more time for a slow message, lock held |
| **NACK** | `modifyAckDeadline(0)` | deadline → 0, **immediate redelivery** to another consumer |
| **Expire** | no ack before the deadline | Pub/Sub assumes the subscriber died, redelivers |

**Measured** (`pubsub_basics.py` §3): pull a message, decline to ack, wait out the 10-second
deadline, pull again — **the same message comes back, nothing having failed.**

> The fix for duplicates is **not** a longer ack deadline. It is to ack promptly, extend the lease
> while genuinely still working, and **make the handler idempotent**.

## 5. Resilience — DLQ, seek, and the missing peek

- **Dead-letter topic** — after N delivery attempts, the message is forwarded instead of blocking
  the pipeline. **It needs its own subscription** or the messages are simply discarded.
  Also catches schema-incompatibility failures in a BigQuery subscription.
- **Seek** — reset the subscription cursor to a **timestamp or snapshot**, to replay acknowledged
  messages or **purge in bulk**. The recovery path after shipping a bad consumer.
- **Peek** — **there is no native peek API.** Pulling without acking is the closest thing, and that
  message will simply be redelivered later.

## 6. Direct integrations — the no-code pipelines

| subscription type | writes to | why it matters |
|---|---|---|
| **BigQuery subscription** | a BigQuery table | **no pipeline to operate at all.** Supports CDC ingestion and schema mapping. **At-least-once only** — dedup downstream or use Dataflow. |
| **Cloud Storage subscription** | GCS objects | auto-batches into Avro, text or JSON files |

**A Dataflow job that only parses JSON and inserts into BigQuery is the commonest
over-engineering in this domain.** A BigQuery subscription does that with nothing to run.

## 7. Pub/Sub vs Kafka

| | **Pub/Sub** | **Kafka** |
|---|---|---|
| architecture | managed, serverless, **global routing** | cluster of brokers (KRaft/ZooKeeper) |
| ops | zero — scales with traffic | capacity planning, partition management |
| ordering | ordering keys, **costs throughput** | **strict within a partition**, free |
| position | server-managed acks | **consumer-owned offsets** → replay |
| pick it when | native GCP async messaging | cross-cloud portability, or lifting an existing cluster as-is |

> A Kafka **partition** is a replayable log with a consumer-owned offset. A Pub/Sub
> **subscription** is a server-managed queue with acks. **Every other difference follows from
> that one.**

## 8. Fundamental operations

```python
# Publishing returns a FUTURE, not a message id.
future = publisher.publish(topic, b'{"trip_id": "T0001"}', station="ST01")
message_id = future.result()

# Pull, handle, then acknowledge. The ack is the contract.
response = subscriber.pull(request={"subscription": sub, "max_messages": 10})
subscriber.acknowledge(request={"subscription": sub,
                                "ack_ids": [m.ack_id for m in response.received_messages]})
```

| # | operation | what it showed |
|---|---|---|
| 1 | create topic + subscriptions | one topic → **2 subscriptions**, both listed |
| 2 | publish and pull | 10 published, 10 pulled, 10 acked |
| 3 | **let an ack deadline expire** | the **same message redelivered** |
| 4 | publish with an ordering key | 5 events, order preserved |
| 5 | attach a dead-letter policy | DLQ after 5 attempts |
| 6 | idempotency | the design consequence of §3 |

## 9. When to use it — and when not

**Use Pub/Sub for** native GCP async messaging, fan-out to several independent consumers, spiky
or global traffic, and anywhere you don't want capacity to plan.

| instead | use | because |
|---|---|---|
| strict ordering over a large key space | **Kafka** partitions | ordering keys throttle throughput |
| replay by arbitrary offset | **Kafka** | the consumer owns its position |
| straight into BigQuery | **BigQuery subscription** | no pipeline at all |
| CDC from a relational database | **Datastream** | reads the binlog directly |
| scheduled file loads | **Storage Transfer / DTS** | this isn't messaging |

## 10. What was actually run

| | |
|---|---|
| `pubsub_basics.py` | ✅ **fully executed** against the emulator, exit 0 |
| Client library | `google-cloud-pubsub` **2.41.0** — the real client, unmodified |
| Cloud resources | **none** — no project, no credentials, no billing |

📝 **Documented, not demonstrated** — the emulator does not implement these: exactly-once
delivery, push subscriptions, BigQuery/GCS subscriptions, seek/snapshots, schema enforcement,
quota behaviour.

> **WSL trap, cost real time:** `which gcloud` may return a **Windows** SDK under `/mnt/c`, which
> cannot run the emulator and fails with a traceback that looks like a bug in your script.
> `find_gcloud()` in the script prefers `/usr/bin/gcloud` and refuses `/mnt/`.
