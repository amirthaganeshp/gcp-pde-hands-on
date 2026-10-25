# Capstone — what the illustration shows

The README explains the *architecture*. This file explains the *script*: what it wires together,
what each injected failure proved, and exactly where the demo stops being real.

---

## `pipeline_end_to_end.py`

**Setup:** the **real Pub/Sub emulator** (started and stopped by the script) feeding **Beam 2.76**
on the `DirectRunner` → Prism, writing station × hour aggregates to a single pipe-delimited text
file, `outputs/capstone/agg` (`window_start|station|sum_minutes`) — not Parquet, not partitioned.

```
Pub/Sub  ->  Beam  ->  outputs/capstone/agg
(emulator)   (windowed by event time)            (station x hour aggregates)
```

**Nothing here is new.** Every component was built in an earlier section. The capstone exists
because the exam's hardest questions — and production — are about the **seams**.

| measured | result |
|---|---|
| messages published and drained from Pub/Sub | **3,000** |
| aggregate rows out | **1,462** |
| hourly windows | 306 |
| stations | 8 |

Output is **station × hour aggregates, not raw trips**. The reporting table is a *derived*
artefact and the raw stream stays the source of truth — which is what makes a bug in the
aggregation recoverable rather than fatal.

---

## The four failures — run, not described

A demo that only shows the happy path teaches that the happy path is the whole path.

### 1. A poison message

One unparseable payload published beside a valid one: **1 parsed, 1 failed**.

> Without a dead-letter topic it is redelivered **forever** — never acked, burning quota and
> filling logs while the real problem stays invisible. In Beam the fix is a **side output**: route
> failures to a second PCollection rather than letting one bad record kill the bundle. Measured in
> [`02_beam_dataflow`](../02_beam_dataflow/) at 4,963 good + **37** dead = 5,000, job succeeded.

### 2. Late data

**40 of 3,000 (1.3%)** arrived after their window closed. At `allowed_lateness = 0` they are
dropped **silently** — no error, no log, no metric. The hourly total is simply wrong and nothing
says so.

**Window size decides how much this is**: the same stream loses **23.9%** in one-minute windows and
**1.3%** in one-hour windows. "Late" is a property of your window, not of the data.

### 3. A schema change — and the two are not equally dangerous

| change | result |
|---|---|
| a **new field** appeared | **harmless** — JSON readers ignore what they do not ask for |
| an existing field became **nullable** | **broke the pipeline** — the code assumed a float |

> **Additive change is the only safe kind.** A **schema on the topic** (Avro or Protobuf) converts
> this into a publish-time rejection instead of a 3 a.m. consumer crash — which is what Pub/Sub
> topic schemas and Kafka's Schema Registry are both for.

### 4. A hot key

Mild here (**1.1×**) and deliberately so. The point is that the same failure already appeared in
five services:

| service | how it shows up | measured |
|---|---|---|
| Kafka | one partition, one consumer | **3 of 5** consumers idle |
| Spark | skewed partition | **34.5×** imbalance |
| Bigtable | one tablet, one node | **1 of 8** tablets |
| Beam / Dataflow | one key, one worker | **5.8×**, fixed by `with_hot_key_fanout` |
| Pub/Sub | an ordering key serialises | by design |

**Five products, one failure mode.** Recognise it by **shape** — *a cluster idle while the job is
slow* — rather than memorising five fixes, because the fix is always the same.

---

## Where this stops being real

| missing | why it matters |
|---|---|
| **Beam reads a bounded snapshot** | a real job reads an unbounded subscription |
| the warehouse is one local text file | no partitions, no clustering, no slots, no billed pruning, no 10 MB minimum |
| no orchestration running | the DAG in `05_orchestration` would trigger this |
| **no IAM at all** | every service runs as you, with no boundary |
| no retry or idempotency | re-running appends; production needs the `MERGE` |
| no monitoring | nothing here would page anyone |
| one machine | no shuffle across workers, so no network cost |

**The bounded-vs-streaming boundary is the important one.** Reading a drained snapshot means the
watermark comes from the data rather than from a live source — so **the late-data figure above is
computed from timestamps, not observed from a runner.**

That is stated rather than glossed, and it is consistent with the negative already recorded in
[`02_beam_dataflow`](../02_beam_dataflow/): late-pane firing did not reproduce on any local runner,
checked across three.

> The services are the easy part. The seams are where the exam — and production — actually lives.
