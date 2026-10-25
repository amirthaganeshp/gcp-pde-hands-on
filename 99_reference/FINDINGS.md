# Findings

Every number here was produced by a script in this repository, on one laptop. Nothing is quoted
from a guide.

The point of collecting them is that **the same few failures recur across unrelated services**, and
seeing them side by side is worth more than the individual numbers.

---

## 1. One failure mode, five products

A hot key means one worker doing all the work while the rest idle. It appears in every processing
and storage service here, wearing a different name each time:

| service | how it appears | measured |
|---|---|---|
| **Kafka** | one partition → one consumer | **3 of 5** consumers given work; 2 idle |
| **Spark** | skewed partition | **34.5×** imbalance; salting → 10.8× |
| **Bigtable** | one tablet → one node | timestamp-first key: **1.0 of 8** tablets |
| **Pub/Sub** | an ordering key serialises | ordering caps parallelism by design |
| **Beam / Dataflow** | one key → one worker | **5.8×** skew; `with_hot_key_fanout` gave identical results |

**Recognise it by shape** — *a cluster idle while the job is slow* — rather than memorising five
fixes, because the fix is always the same: spread the key, or accept the serialisation.

Note Spark's salting only got 34.5× down to **10.8×**. It helps; it does not solve.

Beam's `with_hot_key_fanout` is the same idea done by the runner: the hot key is pre-reduced
across 16 shards before a final merge. Checksums from both plans were **identical (132,651)** —
it changes the **plan**, never the answer. It cannot help `GroupByKey`, because only a Combine
splits into partial aggregations.

## 2. Failures that raise nothing

The most expensive category. Every one of these produces a plausible-looking result and no error:

| what fails silently | measured |
|---|---|
| **late data dropped** at `allowed_lateness = 0` | **23.9%** of the stream in 1-min windows, **1.3%** in 1-hour |
| **a naive CDC merge** | 464 rows against a truth of 461 — a row-count check *passes* |
| **a cache evicting** | **4,517 of 5,000** keys written OK, then discarded |
| **partition pruning not happening** | a function around the partition column scans everything, correct answer returned |
| **ordering enabled on one side only** | Pub/Sub silently gives no ordering |
| **a DLQ topic with no subscription** | poison messages dead-lettered into the void |
| **a Beam closure counting into a list** | DoFns run in worker processes — the list stays **empty** and the script prints confident zeros |
| **fusion capping parallelism** | 200 in → **40,000** out, all on the input's 200 threads, no error |
| **an emulator that was never stopped** | `proc.terminate()` killed the gcloud *wrapper*; the java child kept the port. **Five orphans**, some running for hours |
| **a `node` that is only on the login PATH** | npx died with `'node': No such file or directory` — which reads as *not installed* |

> The CDC one is the sharpest: **464 vs 461**. Close enough to pass a sanity check, with 6 stale
> values and 3 resurrected deletes inside it.

## 3. Defaults nobody chose

| default | consequence | measured |
|---|---|---|
| `spark.sql.shuffle.partitions = 200` | 8 groups spread over **200 partitions** — 192 empty, each with a task | ✔ |
| Beam `DirectRunner` | is a *façade* — `SwitchingDirectRunner` delegated to **Prism** | ✔ |
| `allowed_lateness = 0` | silent drops, see above | ✔ |
| Pub/Sub at-least-once | redelivery is **normal**, not an error | ✔ |
| Airflow `all_success` | a skipped branch makes the whole DAG `skipped` | ✔ |

> 📝 **Documented, not measured — kept out of the tables above on purpose.** BigQuery ML's
> `AUTO_SPLIT` uses **no evaluation set at all under 500 rows** (so `ML.EVALUATE` scores the training
> data — a failure that raises nothing), and above that splits **randomly**, which leaks the future
> on time-ordered data. This is from Google's `CREATE MODEL` documentation:
> [`09_ml_integration/01_bigquery_ml/bqml_patterns.sql`](../09_ml_integration/01_bigquery_ml/bqml_patterns.sql)
> was **never submitted**, so no number here came from running it.

## 4. Things that are crossovers, not preferences

Four decisions that look like judgement calls and are arithmetic:

| decision | crossover |
|---|---|
| online transfer vs **Transfer Appliance** | 10.6 TB at 100 Mbps · **106 TB at 1 Gbps** |
| **on-demand vs capacity** BigQuery | **702 TiB** scanned/month · 421 TiB with a 3-year commitment |
| **logical vs physical** storage billing | exactly **2.0×** compression |
| **Standard vs Nearline** storage class | **1.6 reads/month** |

The transfer one is the starkest: **100 TB takes 132 days at 100 Mbps and 1 day at 10 Gbps.** Same
data, 100× difference, from the link alone.

## 5. Counter-intuitive results

**Archive storage can be 17× *more* expensive than Standard.** 1 TB deleted after one day:
Archive **$14.95**, Standard **$0.89** — the 365-day minimum duration is billed regardless.

**Hashing does not reduce re-identification risk.** Pseudonymising 50,000 identifiers preserved
**100.0%** of their uniqueness. It has to — a hash is a function. "We hashed the IDs so it's
anonymous" is false.

**Aggregation is not anonymisation either.** Singletons appear at **five** quasi-identifiers and
reach **36% of all groups** at six. Nobody adds a *dangerous* column; they add a *useful* one.

**Field promotion beats salting.** Bigtable: `station#time` reached **7.9 of 8** tablets against
salting's 8.0 — a 0.1 difference for the cost of destroying every prefix scan.

**A static alert threshold is not fixable by tuning.** Best static: **4% precision** (91 alerts, 87
false). Best seasonal baseline: **40%**. The metric's busiest hour is **21×** its quietest, so no
single number separates *quiet* from *broken*.

**Partitioning is a storage-cost decision.** Long-term storage is 50% off after 90 days *untouched*
— so a pipeline that rewrites a whole table daily never qualifies, while date partitions let
everything older age into the discount.

## 6. Measured results by section

| section | headline |
|---|---|
| `01_ingestion` | redelivery after a 10 s ack deadline, same payload; Kafka 3 of 5 consumers idle |
| `02_beam_dataflow` | sliding 1h/30m = **2.00×** the element-window pairs; sessions **7,968 → 151** by gap alone |
| `02_beam_dataflow` (batch) | combiner lifting: `add_input` **50,000** pre-shuffle vs `merge` **8** post = **6,250×**; DLQ 4,963 + **37** = 5,000, job succeeded |
| `03_bigquery` | column projection **11.8×**, partition pruning **13.3×**, clustering **6.2× vs 1.0×** |
| `03_bigquery` (Dataform) | **6 actions, 0 errors, 3 ref()-resolved edges**, compiled with **0 BigQuery connections**; a 1-char typo in a `ref()` caught as **2 errors** |
| `04_managed_spark` | 8 groups → 200 partitions; skew 34.5×; broadcast removed the shuffle |
| `05_orchestration` | quiet day ended **success**, not skipped — trigger rule doing its job |
| `06_storage_decisions` | Archive 17× worse for one day; 4,517 keys evicted; Firestore emulator too permissive |
| `07_migration_cdc` | naive merge 464 vs 461; 100 TB = 132 days or 1 day |
| `08_sharing_and_viz` | singletons at 5 dimensions; k=50 keeps **0%** of the data |
| `09_ml_integration` | 📝 **nothing executed** — `bqml_patterns.sql` was never submitted; see the documented `AUTO_SPLIT` note in §3 |
| `10_governance_security` | hashing preserved **100%** uniqueness; bucketing 54.6% → 0% at risk |
| `11_ops_cost_monitoring` | static alerts **4%** precision vs seasonal **40%** |
| `12_capstone` | 3,000 → 1,462 aggregates; the nullable field broke it, the new field did not |

## 7. Honest negatives — kept, not tuned away

**Late-pane firing did not reproduce on any local runner.** TestStream's on-time pane fires; no
late pane ever did, even at `allowed_lateness = 3600`. Checked across three runners —
`DirectRunner` (→ Prism) and `BundleBasedDirectRunner` behaved identically at both settings, and
`FnApiRunner` raised `NotImplementedError` for TestStream entirely. The on-time half is verified;
the late half is **unverified locally**, and section 5b measures the same exposure from the data
side instead.

**The Firestore emulator accepted queries production would reject** — it creates composite indexes
on demand and did not enforce the ordering rule at all. Documented as a finding rather than worked
around: "it worked locally" carries less weight here than anywhere else.

**Salting does not solve skew** — 34.5× → 10.8×, not → 1×.

**A duration window longer than your incidents cannot see them.** Requiring consecutive breaches
removes flapping and starts missing single-period outages.

## 8. Where the narration was wrong before the output corrected it

Recorded because the habit is the transferable part, not the individual slips. In each case the
script's own output contradicted the text written alongside it:

| claim | what the output said |
|---|---|
| "station-first spreads across tablets" | **1 of 8** — the tablet model only read the first byte, and measured rest rather than writes |
| "the summary: all consumers active" | **0** — hardcoded rather than derived |
| "transformations return in microseconds" | **118.8 ms** |
| "broadcast join has no Exchange" | `True` — `BroadcastExchange` matches the substring `Exchange` |
| "100 TB takes over three years" | **132 days** — the three-year figure was the 1 PB row |
| "a group of one is a person" | **0 singletons** — three dimensions was not enough to produce any |
| "the third query fails" | it **succeeded** — the emulator allowed it |

**Read the output against the narration.** Seven times in twelve sections, the numbers disagreed
with the sentence next to them — and every one was caught that way rather than by review.

## 8b. What running the whole list end to end actually found

The run-list was executed as a single batch, **21 items, every exit code recorded**. Result:
**21 of 21 pass, 170 seconds total.** Getting there surfaced three things that individually
passing scripts had hidden:

**1. Every emulator was being leaked.** `proc.terminate()` killed the `gcloud beta emulators
start` *wrapper*, orphaning the java (or Go) child that actually holds the port. Five orphans
were left behind, the oldest running **more than five hours** — while four READMEs claimed each
script "starts and stops its own emulator". Fixed by giving the wrapper its own process group
(`start_new_session=True`) and signalling the **group**, with a SIGKILL escalation if the port
is still held.

**2. A login shell was hiding a broken script.** `compile_check.py` passed every manual test,
because those used `bash -lc`. In the non-login shell the batch used, npx failed instantly with
`/usr/bin/env: 'node': No such file or directory`. **If you only test interactively, you are not
testing what CI runs.**

**3. Nearly every runtime estimate was wrong**, and all in the same direction — overstated.
Spark claimed ~90 s and took **16 s**; the capstone claimed ~60 s and took **6 s**; Bigtable
claimed ~25 s and took **2 s**; one Beam script claimed ~3 min and took **27 s**. They had been
written from impression rather than measurement. All now carry measured values.

> The general lesson: **a suite of individually-passing scripts is not a passing suite.** Nothing
> above is visible until you run them together, in one shell, and check what is left behind.

## 9. A note on reading any of this

Every number is **one machine, one synthetic dataset, one configuration**. Prices are approximate
list prices that move. The crossovers and the mechanisms transfer; the digits do not.

The transferable claim is not any single figure. It is that **these things are cheap to measure and
frequently surprising**, and that a service you have only read about is a service whose failure
modes you do not know.
