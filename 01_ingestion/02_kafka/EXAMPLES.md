# Kafka — what the illustration shows

The README explains the *service*. This file explains the *script*: what it sets up, what it
measures, and which exam idea each measurement makes concrete.

---

## `kafka_basics.py`

**Setup:** a **real Kafka broker** — 4.3.1 in **KRaft mode, no ZooKeeper** — **started and stopped
by the script itself.** The broker must already be unpacked at `~/kafka`; the script does not
download it, and says how to fetch the *current* release if it is missing.
Client is `confluent-kafka` (librdkafka 2.15.1) on OpenJDK 21. No cloud, no managed service.

| § | it does | measured | the exam idea |
|---|---|---|---|
| 2 | creates a topic with 3 partitions | `[0, 1, 2]` | the partition is the unit of everything |
| 3 | produces 45 messages across 9 keys | each key → **exactly one** partition | same key, same partition, ordered |
| 4 | runs consumer groups of **3** and **5** | 3 get work; **at 5, two sit idle** | **partition count caps consumers** |
| 5 | reads from offset 0, rewinds, reads again | 45 then **45, identical** | the consumer owns its position |
| 6 | reads one partition in order | ordered ✅ | ordering is *per partition*, never global |

## §4 — the ceiling, measured

```
group of 3 over 3 partitions : assigned {0:1, 1:1, 2:1}  -> 3 of 3 given work
group of 5 over 3 partitions : assigned {0:1, 1:1, 4:1}  -> 3 of 5, TWO IDLE
```

**Adding consumers past the partition count does nothing.** Two processes sat connected, healthy
and consuming zero. Scaling a Kafka consumer means raising the *partition* count, which is a
topic-level decision made in advance — and you cannot reduce it later.

## §3 — keys spread, volume does not

Nine keys hashed over three partitions:

```
messages per partition: {0: 20, 1: 5, 2: 20}      spread 5 to 20 (4.0x)
```

**The hash distributes keys evenly; it knows nothing about how much traffic each key carries.**
Three keys landing together on one partition is enough to produce a 4× imbalance at this tiny
scale. This is the same failure as a Spark skewed key or a Bigtable sequential row key — see
[`99_reference/FINDINGS.md`](../../99_reference/FINDINGS.md) §1.

## Two bugs this script caught

**"Assigned" and "received" are different numbers.** An earlier version conflated them: a consumer
can be *assigned* a partition and receive **nothing**, because that partition is empty. The run
printed `0` received while the hardcoded summary still claimed "all active" — a narration
contradicting its own output. Both numbers are now printed separately.

**Rebalances take real time.** A group's first join waits for the coordinator to assign partitions.
An impatient poll loop reports a false zero, which is exactly what happened before the timeout was
raised to 30 s.

## Why the script deletes the topic first

```
run twice against the same topic: 45 produced, 75 read, ordering check False
```

**The log persists.** The second run appended to the first run's messages and two runs' ids
interleaved. The script now deletes and recreates the topic before producing — **and that step
exists because Kafka retains**, which is the whole distinction from Pub/Sub showing up as an
operational detail.

## What one local broker cannot show

Not demonstrated, and not simulated: replication and ISR behaviour (this is a single broker,
RF=1), leader election and failover, log compaction over time, transactions and exactly-once
semantics, Kafka Connect, Schema Registry, and anything about **Managed Service for Apache
Kafka** — which is this same software with Google operating the brokers.
