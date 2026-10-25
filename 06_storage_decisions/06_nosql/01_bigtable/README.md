# Bigtable — row-key design

> **Domain 3 — Storing the Data (20%)** · Success Guide pp. 30–33 · Ultimate §3.3
> **Runtime:** ~2 s · **Needs:** `google-cloud-bigtable`, the Bigtable emulator, Java

```bash
python 06_storage_decisions/06_nosql/01_bigtable/row_key_design.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

The single most-tested storage topic on the exam, and the one with the least room for a second
chance: **the row key cannot be changed after the fact.**

---

## 1. What it is

Bigtable is a **sparse, distributed, sorted map**. A petabyte-scale key-value store with
single-digit-millisecond reads, no schema enforcement, and **exactly one index — the row key.**

No secondary indexes. No joins. No query planner. If an access pattern cannot be expressed as a
prefix or range of the row key, Bigtable serves it with a full table scan — which is why the key
*is* the schema rather than part of it.

## 2. Components

| component | what it is |
|---|---|
| **Row key** | The only index. Bytes. **Immutable once the table has data.** |
| **Column family** | A group of columns stored together, with its own GC rule. Few and stable. |
| **Column qualifier** | The column name. Arbitrary bytes, created on write — thousands are fine. |
| **Cell** | A versioned value. Every cell carries a timestamp. |
| **Tablet** | A contiguous range of the sorted key space, served by one node. |
| **GC rule** | Per-family: max versions, max age, or both. |

**Rows are stored sorted by key, as bytes.** Every design rule below follows from that one fact —
including that it sorts *lexicographically*, so `'10'` comes before `'9'` and an unpadded integer
key does not range-scan the way you expect.

## 3. Instance anatomy

| layer | what it is |
|---|---|
| **Instance** | The container. Holds one or more clusters. |
| **Cluster** | A zonal set of **nodes**. Throughput scales linearly with node count. |
| **Node** | Serves a set of tablets. **Storage is separate from nodes** — adding nodes redistributes tablets, it does not move data. |
| **Storage type** | **SSD** (default, low latency) or **HDD** (cheap, scan-heavy archives). **Chosen at creation and immutable.** |
| **Replication** | Extra clusters in other zones/regions, kept eventually consistent. |
| **App profile** | How a client routes: **single-cluster** (strong consistency, manual failover) or **multi-cluster** (automatic failover, eventual consistency). |

**Replication buys availability and read isolation**, not consistency. The classic pattern is a
serving cluster and a batch-analytics cluster in one instance, each with its own **single-cluster**
app profile, so a heavy scan never touches serving latency.

> **Multi-cluster routing gives up read-your-writes.** If the requirement says strong consistency,
> the answer is single-cluster routing — and you accept manual failover.

## 4. Fundamental operations

| measured | result |
|---|---|
| point read (exact key) | 1 row, **1.6 ms** |
| prefix scan (`ST05#`) | 493 rows, **68 ms** |
| full table scan | 4,000 rows, **490 ms** |

The point read and prefix scan are cheap because matching rows are **adjacent**. The full scan is
what every query that does not match the row key becomes.

## 5. Filters — server-side, and the composition rules

Returning every cell is wasteful. Filters run **on the server before the response crosses the
network**, which is a throughput and cost decision, not just a convenience.

| filter | logic | mechanism |
|---|---|---|
| **Chain** | **AND** (intersection) | filters run **in sequence** — each one's output is the next one's input |
| **Interleave** | **OR** (union) | the same input row goes through **every** filter in parallel, results merged |
| **Condition** | if/then/else | a predicate filter chooses between a true-branch and a false-branch filter |

```
Chain(FamilyRegex("telemetry"), ValueRegex("error"))
  -> only telemetry cells whose value contains "error"        (AND)

Interleave(ColumnRegex("email"), ColumnRegex("phone"))
  -> email cells AND phone cells, both returned               (OR)
```

> **Interleave can emit duplicate cells.** Because each filter sees the *original* row, a cell
> matching two branches appears twice in the output. Chain cannot do this — it narrows
> monotonically. That asymmetry is the tested detail.

## 6. Nuances — the part worth reading

**Hotspotting is a write-time problem, and it is measurable.** Four key designs, 4,000 trips
arriving in time order, 8 tablets. For each burst of 100 consecutive writes, how many distinct
tablets received them?

| design | tablets per burst | worst burst | spread |
|---|---|---|---|
| `timestamp#trip_id` | **1.0** | 1 | **12%** |
| `station#timestamp` | 7.9 | 7 | 99% |
| `station#~timestamp` | 7.9 | 6 | 99% |
| `hash#station#timestamp` | 8.0 | 8 | 100% |

**A timestamp-first key sends every concurrent write to one tablet on one node** while the rest of
the cluster idles. That is the classic Bigtable mistake, and it is *invisible in testing* — a small
dataset fits one tablet anyway, so the design only fails at the scale you bought Bigtable for.

**Field promotion gets you 99% of the benefit of salting without the cost.** Moving `station` to the
front took the spread from 12% to 99%. Salting reached 100% — a 1-point gain for a large price:

> **Salting destroys range scans.** With `hash#station#time`, the hash is leftmost, so a scan for
> one station must read **every salt bucket**. You trade a cheap prefix scan for a fan-out. Salt
> only when the access pattern is genuinely point reads; if you range-scan, promote a real field.

**Reversing the timestamp keeps the prefix and gives you newest-first.** `station#~timestamp` sorts
recent rows first within each station, so "latest N for this station" is a prefix scan with a limit
rather than a scan-and-sort.

**Keep row keys short.** The key is stored in *every cell*, so a verbose key multiplies storage
across the whole table.

**Few column families, many qualifiers.** Families are heavyweight and fixed at design time;
qualifiers are created on write and cost nothing. Modelling "one family per field" is the wrong way
round. Keep families **under ~100**, and group columns that are **read together** — Bigtable
compresses within a family, so co-locating related columns is a storage win as well as an I/O one.
**IAM and garbage-collection rules attach to the family, never to a single column.**

**Key Visualizer is the diagnostic for all of this.** It renders a heatmap of key space against
time, so a hotspot appears as a bright vertical band. It is the tool that turns "writes are slow"
into "your key is sequential".

**There is no fix after the fact.** No index to add later. The options are rewriting the table, or
maintaining a second table keyed differently and writing to both.

> Same shape as a **Kafka hot partition** ([`01_ingestion/02_kafka`](../../../01_ingestion/02_kafka/))
> and a **Spark skewed key** ([`04_managed_spark`](../../../04_managed_spark/)) — one key, one
> worker, no parallelism. Three services, one failure mode.

## 7. When to use it — and when not

| situation | reach for |
|---|---|
| high-throughput point reads/writes by a known key | **Bigtable** |
| time series, IoT, ad-tech, user profiles at scale | **Bigtable** |
| **analytical scans and aggregation** | **BigQuery** — Bigtable has no aggregation |
| you need joins, or ad-hoc query flexibility | **BigQuery** or **Spanner** |
| you need transactions across rows | **Spanner** — Bigtable is single-row atomic only |
| document model, mobile sync, small scale | **Firestore** |

**Bigtable is single-row atomic and nothing more.** No multi-row transactions. That, plus the
absence of aggregation, is usually what rules it out.

## 8. What was actually run

| | |
|---|---|
| `row_key_design.py` | ✅ **fully executed**, exit 0 |
| Emulator | Bigtable emulator from the gcloud SDK, started and stopped by the script |
| Client | `google-cloud-bigtable` **2.47.0** — the real client |
| Cloud resources | **none** |

**Section 3's tablet model is a simulation, and it was wrong the first time.** Tablets are modelled
by splitting the *sorted key space* into 8 ranges at quantiles of the actual keys — which is what
real Bigtable does when it splits to balance storage.

The first version used `ord(key[0]) % 8`, and it was wrong twice over: it looked only at the first
byte, so every `ST..` key landed on one tablet and **station-first scored as badly as
timestamp-first**; and it measured where rows come to *rest*, when hotspotting is about where
concurrent *writes* land. The current version measures distinct tablets per burst of 100
consecutive writes, in arrival order — which is the thing that actually hurts.
