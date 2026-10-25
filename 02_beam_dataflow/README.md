# Dataflow (Apache Beam)

> **Domain 2 — Ingesting and Processing the Data (25%)** · Success Guide pp. 73–104 · Ultimate §2.4
> **Runtime:** ~5 s + ~30 s + ~10 s · **Needs:** `apache-beam` only — no JVM, no cloud

```bash
python 00_setup/make_data.py                         # once
python 02_beam_dataflow/01_the_beam_model.py         # the transform vocabulary
python 02_beam_dataflow/02_windows_and_watermarks.py # streaming semantics
python 02_beam_dataflow/03_batch_processing.py       # batch mechanics
```

Walk-through of what each script illustrates: **[EXAMPLES.md](EXAMPLES.md)**.

The heaviest section in this repository, because the exam weights it heaviest.

---

## 1. What it is

**Dataflow has no programming model of its own — it runs Apache Beam.** You write Beam; Dataflow
translates it into an optimised job graph, provisions Compute Engine workers, runs it, and tears
them down. So "learning Dataflow" splits cleanly in two:

| | where it runs | how this repo covers it |
|---|---|---|
| **Beam semantics** — transforms, windows, triggers | anywhere, including here | ✅ executed locally |
| **Dataflow service** — fusion, shuffle, autoscaling, FlexRS | Google's backend only | 📝 documented, never faked |

Only the runner changes between the two:

```python
PipelineOptions(runner="DirectRunner")   # here, free, one machine
PipelineOptions(runner="DataflowRunner") # managed, autoscaled, billed
```

**Bounded vs unbounded input is the only thing that makes a pipeline batch or streaming.** The
code is otherwise the same, which is the single most useful fact in this section.

## 2. Anatomy — what happens when you submit a job

| # | stage | what the service does |
|---|---|---|
| 1 | **Graph translation** | The SDK turns your code into a JSON DAG. Your Python does not run on the workers as-written. |
| 2 | **Step fusion** | Consecutive steps are fused into one so intermediates are never materialised. Free speed — until it isn't (§6). |
| 3 | **Worker provisioning** | Compute Engine VMs start and receive the fused graph. |
| 4 | **Execution + dynamic work rebalancing** | Work is split into **bundles**. A straggler's *unprocessed* work is split and handed to idle workers. |
| 5 | **Teardown** | Batch only: workers are destroyed, billing stops. Streaming runs until drained or cancelled. |

**Dynamic work rebalancing cannot subdivide a single record.** One pathological record stalls the
job no matter how many workers you add — the same reason a hot *key* defeats autoscaling.

### The vocabulary

| term | what it is |
|---|---|
| **Pipeline** | The DAG itself. |
| **PCollection** | A distributed, **immutable** dataset. Bounded or unbounded. |
| **PTransform** | An operation producing a *new* PCollection. |
| **Bundle** | The unit of work and of retry. Failure retries the bundle, not the element. |
| **Worker / VM / node** | The Compute Engine instance executing the graph. |

### Autoscaling

| flag | effect |
|---|---|
| `--num_workers` | Initial worker count. With `--autoscaling_algorithm=NONE`, a fixed pool. |
| `--max_num_workers` | Hard cap — how you stop runaway cost or protect a downstream API's quota. |
| `--autoscaling_algorithm` | `THROUGHPUT_BASED` (streaming default) or `NONE`. |
| **Dataflow Prime** | **Vertical** autoscaling: watches OOMs and replaces workers with higher-RAM ones. |

## 3. The transform vocabulary

| transform | what it does | the catch |
|---|---|---|
| **ParDo** / **DoFn** | Map, FlatMap and Filter in one primitive — 0, 1 or many out. | The DoFn is the code; the ParDo is the transform. |
| **GroupByKey** | Groups all values sharing a key into one iterable. | **A hot key OOMs one worker** — the whole value list must fit. |
| **CombinePerKey** | Aggregates with mapper-side pre-aggregation. | Only works for associative/commutative ops. |
| **CoGroupByKey** | The real join — a SQL JOIN across PCollections. | Shuffles **both** sides. |
| **Side input** | Broadcasts a small dataset into every worker's memory. | Too big ⇒ every worker OOMs at once, not just one. |
| **Side output** | One ParDo routing elements to different PCollections. | **This is how you build a dead-letter queue.** |
| **Flatten** | Union of same-typed PCollections. | No grouping, no dedup. |
| **Partition** | Splits into N PCollections by a function. | **Exhaustive and disjoint** — unlike N filters. |
| **Reshuffle** | Forces a materialisation point. | Breaks fusion deliberately (§6). |

**Measured** (`03_batch_processing.py`, 50,000 records, 8 keys):

| | result |
|---|---|
| GroupByKey | **50,000** raw values materialised after the group |
| CombinePerKey | `add_input` **50,000** pre-shuffle vs `merge_accumulators` **8** post-shuffle — **6,250×** |
| Side output DLQ | 4,963 parsed + **37** dead-lettered = 5,000, **nothing lost, job succeeded** |
| Flatten / Partition | 8,667 union → **2,324 / 5,070 / 1,273**, exhaustive |

## 4. Batch — bounded data

| mechanism | what it buys | the constraint |
|---|---|---|
| **Dataflow Shuffle** | Moves grouping/joining **off worker disks** onto the service backend. | The fix for shuffle-bound OOM and disk I/O. `--experiments=shuffle_mode=service` |
| **FlexRS** | Preemptible + regular VM mix for non-urgent batch. | Queued, **guaranteed to start within 6 hours**. **Requires service-side shuffle** — otherwise a preemption loses on-disk intermediates. |
| **Dynamic rebalancing** | Straggler work redistributed automatically. | Cannot split one record. |

**Why FlexRS requires Dataflow Shuffle** is the exam's favourite causal chain here: preemptible
workers vanish without warning; if intermediate results lived on their local disks they'd vanish
too; service-side shuffle means there is nothing on the worker to lose.

## 5. Streaming — unbounded data

| concept | what it is |
|---|---|
| **Event time vs processing time** | When it happened vs when a worker saw it. |
| **Watermark** | The runner's estimate that no more data will arrive for a window. Refuses to advance if a step fails, so incomplete results are never emitted. |
| **Windows** | Fixed/tumbling · sliding/hopping · session (per-key, gap-driven) · global. |
| **Triggers** | *When* a window emits: default (on watermark), early/speculative, late. Composite via `AfterFirst`/`AfterAll`/`AfterEach`. |
| **Panes** | The output unit — early, on-time, late. |
| **`allowed_lateness`** | How long window state is kept. **State bloat**: 7 days' lateness on a 5-minute window keeps enormous state open. |
| **Accumulation mode** | Discarding (deltas — append-only sinks) vs accumulating (running totals — upsert sinks) vs accumulating-and-retracting. |

> **The double-counting trap:** accumulating mode into an **append-only** BigQuery table
> double-counts. Discarding mode into a sink that **overwrites** under-counts. The mode must match
> what the sink does with a repeated pane.

**Streaming Engine** moves state, windowing and shuffle to the backend — faster autoscaling, no
worker OOM. **Exactly-once**: Dataflow tags each message and keeps a bloom filter of seen IDs, so
a Pub/Sub redelivery after a worker crash is discarded.

**Measured** (`02_windows_and_watermarks.py`):

| | result |
|---|---|
| Event-time vs processing-time hour | **273 trips (0.5%)** land in a different hour |
| Sliding 1h/30m vs fixed 1h | **2.00×** the element-window pairs |
| Sessions by gap (5/15/60 min) | **7,968 / 1,454 / 151** |
| Late events by window size | **23.9% / 7.6% / 1.3%** |

## 6. Nuances — the part worth reading

**`DirectRunner` is not a runner.** It resolves to `SwitchingDirectRunner`, a façade that inspects
the pipeline and delegates — on Beam 2.76 it handed these to **Prism**. "It worked on DirectRunner"
means less than it sounds like.

**Beam executes DoFns in worker processes.** Appending to a list in a closure measures *nothing* —
the list in your process stays empty and the script reports confident zeros. Use metrics or file
sinks. This repo made that mistake once; every count in `03_batch_processing.py` is a counter.

**Fusion has to be broken in two shapes**, both via `Reshuffle()`:
- **High fan-out** — 200 elements in, 40,000 out (measured). Fused, parallelism stays capped at the
  *input* count of 200.
- **Non-splittable source** — one gzipped file cannot be sharded, so the fused chain runs
  single-threaded and the job will not scale however many workers you allow.

**Hot keys** — `with_hot_key_fanout` pre-reduces the hot key across N shards before a final merge.
Measured at 5.8× skew: identical checksums (132,651) from both plans, because it changes the
**plan**, never the answer. It cannot help `GroupByKey` — only a Combine can be split into partial
aggregations.

**Side input vs CoGroupByKey** is the join decision the exam tests: small side in memory ⇒ side
input, and the big side never shuffles. Both sides large ⇒ CoGroupByKey, no choice.

**A raising DoFn does not skip the element.** The bundle retries; four failures kill the job. One
malformed row can destroy a six-hour pipeline that had already done the work — hence the DLQ.

## 7. Operating a job

| action | effect | applies to |
|---|---|---|
| **Cancel** | Stops immediately, **discards in-flight data**. | batch + streaming |
| **Drain** | Stops ingestion, advances the watermark to infinity, closes windows, finishes buffered data. | **streaming only** |
| **Force cancel** | Terminates a stuck job, abandons cleanup — **can leak VMs**. | both |
| **Update in place** | `--update` with the same `--job_name`; state is transferred to new workers. | streaming |

**Drain to deploy new code. Cancel only when data loss is acceptable.**

| symptom | likely cause | remedy |
|---|---|---|
| System Lag spikes, no output | slow synchronous external call, or a hot key | async I/O; fan out the key |
| Workers restart, OOM in logs | worker-side state | enable Streaming Engine; cut `allowed_lateness`; Dataflow Prime |
| Stuck retrying one message | poison pill | dead-letter queue via side output |
| Job won't scale up | non-splittable input, hot key, deleted staging files | `Reshuffle`; fan out; fix the bucket lifecycle rule |
| `DEADLINE_EXCEEDED` / `UNAVAILABLE` | worker-to-worker comms blocked | allow TCP **12345–12346** for the Dataflow network tags |

Useful flags: `--experiments=shuffle_mode=service`, `--num_workers`, `--disk_size_gb`,
`--worker_disk_type` (pd-ssd).

### Templates — how a pipeline becomes a reusable artifact

| | **Classic** | **Flex** |
|---|---|---|
| packaged as | JSON file in **Cloud Storage** | **Docker image** in Artifact Registry |
| graph built | at **build** time (static) | at **runtime** (dynamic) |
| custom dependencies | awkward — stage via GCS | easy — bake into the Dockerfile |
| dynamic topology | **not supported** | **fully supported** |

**Reach for Flex** when the pipeline shape depends on a parameter or a config file read at launch,
or when you need system-level dependencies (e.g. C++ libraries) on the workers.

Templates are what make Dataflow event-driven. Trigger them with **Cloud Scheduler** (cron → REST
API) for time-based batch, **Eventarc + Cloud Functions** for "a file landed in this bucket", or
**Composer** (`DataflowTemplateOperator` / `DataflowStartFlexTemplateOperator`) when the job is one
step in a larger DAG.

## 8. When to use it — and when not

**Use Dataflow when** you need one codebase for batch *and* streaming; you want serverless with no
cluster to size; or you need event-time correctness — windows, watermarks, late data.

**Don't use it when:**

| instead of Dataflow | use | because |
|---|---|---|
| parsing JSON → BigQuery | **Pub/Sub BigQuery subscription** | no pipeline to operate at all — the commonest over-engineering in this domain |
| transforming data already in BigQuery | **BigQuery SQL** | don't move data out to transform it |
| an existing Spark/Hadoop estate | **Managed Spark** | lift-and-shift, keep the code |
| visual prep by non-engineers | **Data Fusion / Dataprep** | Dataprep runs on Dataflow underneath anyway |

## 9. What was actually run

| file | status | covers |
|---|---|---|
| `01_the_beam_model.py` | ✅ executed | pipeline/PCollection/PTransform, Map/FlatMap/Filter, grouping, side inputs, branching |
| `02_windows_and_watermarks.py` | ✅ executed | event time, four window types, watermarks, triggers, lateness, accumulation |
| `03_batch_processing.py` | ✅ executed | bounded sources, DLQ side outputs, GBK vs Combine, CoGroupByKey vs side input, Flatten/Partition, hot-key fanout, fusion |

📝 **Documented, not demonstrated** — no honest local proxy exists: Dataflow Shuffle, FlexRS,
dynamic work rebalancing, horizontal/vertical autoscaling, Streaming Engine, Dataflow Prime,
templates, drain/update-in-place.

**Honest negative:** late-pane firing never reproduced on any local runner, checked across three.
Kept in `99_reference/FINDINGS.md` rather than tuned away.
