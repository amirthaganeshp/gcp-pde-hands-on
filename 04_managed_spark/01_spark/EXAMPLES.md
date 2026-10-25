# Managed Spark — what the illustration shows

The README explains the *service*. This file explains the *script*: what it sets up, what it
measures, and which exam idea each measurement makes concrete.

---

## `spark_basics.py`

**Setup:** real Apache Spark, running locally via PySpark on Java 21 — **the same engine the
managed service runs**. No cluster, no project, no billing.

| § | it does | measured | the exam idea |
|---|---|---|---|
| 1 | chains 3 transformations, then calls `count()` | **143 ms** vs **714 ms** | **lazy evaluation** — only an action runs anything |
| 2 | checks partitions after a narrow step | 2 → **2** | narrow needs only the local partition |
| 3 | checks partitions after a wide step | 2 → **200** | the shuffle, and a default nobody chose |
| 4 | counts the groups actually produced | **8** | 192 of those 200 partitions are empty |
| 5 | skews one key across 8 partitions | **34.5×** imbalance | the hot key |
| 6 | salts the hot key | **10.8×** | it helps — **it does not solve** |
| 7 | inspects the plan for a shuffle join | shuffle **True** | wide transformation |
| 8 | inspects the plan for a broadcast join | shuffle **False** | the small side was copied instead |

## §1 — why timings mislead

```
three chained transformations : 143 ms      <- nothing ran
the count() action on them    : 714 ms      <- the work
```

The 143 ms was Python building a plan and resolving a schema. **Any benchmark that times
transformations rather than actions is measuring the wrong thing** — and this is how "Spark is
fast" conclusions get drawn from code that never executed.

## §3–4 — `spark.sql.shuffle.partitions = 200`

Eight groups. Two hundred partitions. **One hundred and ninety-two of them empty**, each still
scheduled as a task.

> Nobody chose 200 — it is the shipped default, and it is wrong in both directions: pure overhead
> on a small job, far too few on a large one. **AQE** exists to coalesce them *after* the shuffle,
> once real statistics are known.

## §5–6 — the honest negative

Salting took skew from **34.5× to 10.8×**, not to 1×. That result is kept exactly as measured.

> A tutorial that shows salting "solving" skew has either picked a friendly example or stopped
> measuring. Splitting a hot key across N sub-keys bounds the damage; it does not make the key cold,
> and the final merge still has to happen.

Compare [`../../02_beam_dataflow/`](../../02_beam_dataflow/), where `with_hot_key_fanout` does the
same thing at the runner level — and where the checksums proved it changes the **plan**, never the
answer.

## §7–8 — the bug this section caught

The obvious way to test for a shuffle is wrong:

```python
# WRONG - a broadcast plan CONTAINS "BroadcastExchange", so this matches
return "Exchange" in plan

# RIGHT - test for what an actual shuffle emits
return ("hashpartitioning" in plan.lower() or "rangepartitioning" in plan.lower())
```

The first version reported "shuffle: True" for the broadcast join — **the exact opposite of the
point the section was making**, in output that otherwise looked entirely plausible. Recorded in
[`99_reference/FINDINGS.md`](../../99_reference/FINDINGS.md) §8.

## What running locally cannot show

Everything above is **Spark semantics**, identical on the managed service. Not demonstrated, and
not simulated: cluster provisioning, YARN and HDFS, secondary Spot workers, autoscaling policies,
graceful decommissioning, EFM, init actions, custom images, Serverless batches, Dataproc on GKE.

Those are properties of a cluster, and one laptop cannot honestly stand in for one.
