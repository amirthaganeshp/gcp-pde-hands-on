# Dataflow — what each illustration shows

The README explains the *service*. This file explains the *scripts*: what each one sets up, what it
measures, and which exam idea the measurement is there to make concrete.

All three run on `apache-beam` alone — no JVM, no project, no billing.

---

## `01_the_beam_model.py` — the transform vocabulary

**Setup:** 50,000 synthetic bike-share trips read from a CSV as a bounded PCollection.

| it does | to show |
|---|---|
| `Filter` trips ≥ 10 min → 36,899 of 50,000 | Filter only ever *removes* — the count can never rise |
| `FlatMap` each trip to its two station events → exactly **2×** | FlatMap changes cardinality, Map cannot |
| Same aggregate via `GroupByKey` and `CombinePerKey` → identical 8 results | same answer, different shuffle cost — set up for script 3 |
| A side input carrying the station lookup | the small-table join, without a shuffle |
| One PCollection consumed by several branches | a PCollection is immutable, so branching is free |

**The point:** ParDo is the only real primitive. Map, FlatMap and Filter are conveniences over it,
and knowing that explains why a DoFn can emit zero, one, or many elements.

## `02_windows_and_watermarks.py` — streaming semantics

**Setup:** the same trips, but replayed on their *event* timestamps. The generator deliberately
made **8.0% of events arrive minutes late** (median lag 11.2 s, p95 423.5 s) — without that tail
none of this would be observable.

| it does | measured | to show |
|---|---|---|
| Bucket by event time vs processing time | **273 trips (0.5%)** land in a different hour | the two clocks genuinely disagree |
| Sliding 1 h every 30 min vs fixed 1 h | **2.00×** element-window pairs | sliding windows duplicate elements by design |
| Session windows at 5 / 15 / 60 min gaps | **7,968 / 1,454 / 151** | the gap parameter *is* the analysis |
| Vary window size, count late arrivals | **23.9% / 7.6% / 1.3%** | "late" is a property of your window, not the data |

**The point:** a watermark is an *estimate*, and `allowed_lateness = 0` drops late data **silently**
— no error, no metric, just a smaller number. The 23.9%/1.3% spread is how much that choice moves.

> **Honest negative:** late-pane firing did not reproduce on any local runner, checked across
> three. The windowing and lateness results above are real; the late-*pane* behaviour is the one
> thing here that needs the service.

## `03_batch_processing.py` — batch mechanics

**Setup:** bounded reads, with a deterministic seed so every number reproduces.

| § | it does | measured |
|---|---|---|
| 1 | Reads a non-growing file | 50,000 — bounded, so workers can be sized and torn down |
| 2 | Injects 37 malformed rows into 5,000, routes them to a **side output** | 4,963 parsed + **37** dead = 5,000, **nothing lost, job succeeded** |
| 3 | Counts `CombineFn` stages either side of the shuffle | `add_input` **50,000** vs `merge_accumulators` **8** → **6,250×** |
| 4 | Same join via `CoGroupByKey` and via a side input | 8 groups both ways — one shuffles both sides, one broadcasts |
| 5 | `Flatten` then `Partition` into 3 | 8,667 union → **2,324 / 5,070 / 1,273**, sums exactly |
| 6 | Skews one key, combines with and without `with_hot_key_fanout` | 5.8× skew, **identical checksums (132,651)** |
| 7 | High fan-out ParDo + `Reshuffle` | 200 in → **40,000** out |

**The points, in order:**

- **§2** A raising DoFn does *not* skip the element — the bundle retries, and four failures kill the
  job. The DLQ is the difference between a finished pipeline and a six-hour loss.
- **§3** This is combiner lifting made visible. 50,000 `add_input` calls happen *before* the
  network; only 8 accumulators cross it. That ratio is the entire argument for `Combine`.
- **§6** Fanout changes the **plan**, never the answer — which is why the checksums must match. It
  cannot help `GroupByKey`, because only a Combine splits into partial aggregations.
- **§7** Fusion is normally free speed. It hurts on high fan-out (parallelism capped at the *input*
  count) and on non-splittable sources (one gzipped file ⇒ one thread).

---

## How to read the measurements

**Every count goes through a Beam Metrics counter, never a Python list.** Beam runs DoFns in
worker processes, so appending to a closure list measures nothing — the list stays empty and the
script prints confident zeros. This repo made exactly that mistake once; see
[`99_reference/FINDINGS.md`](../99_reference/FINDINGS.md) §2.

Numbers that would need the managed service — shuffle throughput, FlexRS savings, autoscaling
behaviour — are **not** simulated anywhere. Script 3 closes by naming them and saying why.
