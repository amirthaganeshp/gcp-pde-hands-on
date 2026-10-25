"""Dataflow BATCH processing: bounded data, and the machinery that makes it fast.

The streaming file next door is about TIME. This one is about VOLUME. Batch
pipelines read bounded data - a file, a table dump - process it, and tear the
workers down. Nothing here needs a watermark, and that changes which parts of
Beam matter.

  1. Bounded vs unbounded, and what the runner can do once it knows
  2. ParDo + side outputs - the dead-letter queue pattern
  3. GroupByKey vs CombinePerKey - what ACTUALLY crosses the network
  4. CoGroupByKey vs side input - two ways to join
  5. Flatten and Partition - union and split
  6. The hot key, and with_hot_key_fanout
  7. Fusion, and why you sometimes have to BREAK it with Reshuffle

EXECUTED IN FULL. Every number printed below was measured on this machine.

NOTE ON MEASUREMENT: every count here goes through a Beam Metrics counter, not
a Python list. Beam executes DoFns in WORKER PROCESSES, so appending to a list
in a closure measures nothing - the list in this process stays empty. That
mistake is easy to make and produces confident, wrong output.

Run:
    python 00_setup/make_data.py             # once
    python 02_beam_dataflow/03_batch_processing.py

Guide reference: Success Guide pp. 80-88 (Dataflow Batch Processing).
"""

from __future__ import annotations

import csv
import logging
import random
from pathlib import Path

for _noisy in ("apache_beam.utils.subprocess_server", "PrismRunner",
               "apache_beam.runners.portability.prism_runner"):
    logging.getLogger(_noisy).setLevel(logging.ERROR)

import apache_beam as beam
from apache_beam.metrics import Metrics, MetricsFilter
from apache_beam.options.pipeline_options import PipelineOptions

ROOT = Path(__file__).resolve().parents[1]
TRIPS = ROOT / "data" / "trips.csv"
STATIONS = ROOT / "data" / "stations.csv"
NS = "batch"


def rule(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def opts() -> PipelineOptions:
    return PipelineOptions(runner="DirectRunner")


def counter_map(name: str):
    """A Map that only increments a counter - the safe way to measure."""
    c = Metrics.counter(NS, name)

    def _f(element):
        c.inc()
        return element

    return beam.Map(_f)


def read_counters(pipeline) -> dict[str, int]:
    res = pipeline.result
    return {m.key.metric.name: m.committed
            for m in res.metrics().query(
                MetricsFilter().with_namespace(NS))["counters"]}


def load_trips() -> list[dict]:
    with TRIPS.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------- 1. bounded
def section_bounded() -> list[dict]:
    rule("1. BOUNDED DATA - what makes this a batch pipeline")
    rows = load_trips()
    print(f"  Read {len(rows):,} trips from a file that is not growing.")
    print("\n  BOUNDED means the runner knows the extent of the input up front, so it can:")
    print("    - split the input into bundles and size the worker pool against it")
    print("    - run to completion and TEAR THE WORKERS DOWN, which stops billing")
    print("    - skip watermarks entirely - a finished file has no concept of 'late'")
    print("\n  On Dataflow the same code reads from GCS instead. The pipeline is identical;")
    print("  the bounded source is the ONLY difference between batch and streaming mode.")
    return rows


# ------------------------------------------------- 2. side outputs as a DLQ
class ParseTrip(beam.DoFn):
    """Parse a row, routing failures to a SIDE OUTPUT rather than raising.

    A DoFn that raises does NOT skip that element. Dataflow retries the bundle,
    and after four consecutive failures the whole job dies. One malformed row
    can therefore destroy a six-hour pipeline that had already done the work.
    The dead-letter pattern is the fix, and the mechanism is a side output.
    """

    DEAD = "dead"

    def __init__(self):
        self.parsed = Metrics.counter(NS, "dlq_parsed")
        self.dead = Metrics.counter(NS, "dlq_dead")

    def process(self, row):
        try:
            minutes = float(row["duration_min"])
            if minutes < 0:
                raise ValueError("negative duration")
            self.parsed.inc()
            yield {"station": row["start_station"], "minutes": minutes}
        except (ValueError, KeyError, TypeError) as exc:
            self.dead.inc()
            # The bad record LEAVES the pipeline intact, carrying its reason.
            yield beam.pvalue.TaggedOutput(
                self.DEAD, {"row": row.get("trip_id", "?"), "reason": str(exc)})


def section_dlq(rows: list[dict]) -> None:
    rule("2. SIDE OUTPUTS - the dead-letter queue")

    rng = random.Random(7)
    corrupted = [dict(r) for r in rows[:5000]]
    victims = rng.sample(range(len(corrupted)), 37)
    for i in victims:
        corrupted[i]["duration_min"] = "" if i % 2 else "-4.0"

    with beam.Pipeline(options=opts()) as p:
        outputs = (p
                   | beam.Create(corrupted)
                   | beam.ParDo(ParseTrip()).with_outputs(ParseTrip.DEAD,
                                                          main="good"))
        outputs["good"] | "CntGood" >> counter_map("dlq_main_out")
        outputs[ParseTrip.DEAD] | "CntDead" >> counter_map("dlq_side_out")

    c = read_counters(p)
    parsed, dead_n = c.get("dlq_parsed", 0), c.get("dlq_dead", 0)

    print(f"  Injected {len(victims)} malformed rows into {len(corrupted):,}.\n")
    print(f"  Main output   : {parsed:,} parsed")
    print(f"  Side output   : {dead_n:,} dead-lettered")
    print(f"  Accounted for : {parsed + dead_n:,} of {len(corrupted):,}"
          f"   -> {'NOTHING LOST' if parsed + dead_n == len(corrupted) else 'MISMATCH'}")
    print("\n  The job SUCCEEDED. Without the side output it would have failed on the")
    print("  first bad row's fourth retry, having already done all the other work.")


# ------------------------------------- 3. GroupByKey vs CombinePerKey (cost)
class CountingMeanFn(beam.CombineFn):
    """A mean that records how often each CombineFn stage is invoked.

    This is the only honest way to show combiner lifting. add_input runs on the
    worker that already HAS the element, before the shuffle; merge_accumulators
    runs after it. add_input >> merge_accumulators means the network carried
    accumulators rather than raw records.
    """

    def __init__(self):
        self.adds = Metrics.counter(NS, "combine_add_input")
        self.merges = Metrics.counter(NS, "combine_merge")

    def create_accumulator(self):
        return (0.0, 0)

    def add_input(self, acc, value):
        self.adds.inc()
        return (acc[0] + value, acc[1] + 1)

    def merge_accumulators(self, accs):
        self.merges.inc()
        total, n = 0.0, 0
        for s, c in accs:
            total += s
            n += c
        return (total, n)

    def extract_output(self, acc):
        return acc[0] / acc[1] if acc[1] else 0.0


class ExplodeGroup(beam.DoFn):
    """Count every value that materialised after a GroupByKey."""

    def __init__(self):
        self.vals = Metrics.counter(NS, "gbk_values")

    def process(self, kv):
        key, values = kv
        n = 0
        for _ in values:
            self.vals.inc()
            n += 1
        yield (key, n)


def section_grouping(rows: list[dict]) -> None:
    rule("3. GroupByKey vs CombinePerKey - what crosses the network")
    pairs = [(r["start_station"], float(r["duration_min"])) for r in rows]
    n_keys = len({k for k, _ in pairs})

    with beam.Pipeline(options=opts()) as p:
        (p | beam.Create(pairs) | beam.GroupByKey() | beam.ParDo(ExplodeGroup()))
    gbk_n = read_counters(p).get("gbk_values", 0)

    with beam.Pipeline(options=opts()) as p2:
        (p2 | beam.Create(pairs) | beam.CombinePerKey(CountingMeanFn())
            | counter_map("combine_keys_out"))
    c2 = read_counters(p2)
    adds, merges = c2.get("combine_add_input", 0), c2.get("combine_merge", 0)

    print(f"  {len(pairs):,} records, {n_keys} distinct keys (stations).\n")
    print(f"  GroupByKey    : {gbk_n:,} raw values materialised after the group.")
    print("                  Every record travelled, then sat in ONE worker's memory.")
    print(f"  CombinePerKey : add_input {adds:,} (pre-shuffle) / "
          f"merge_accumulators {merges:,} (post-shuffle)")
    if merges:
        print(f"                  {adds / merges:,.0f}x more work done BEFORE the "
              f"shuffle than after.")
    print("\n  Same answer, very different cost. GroupByKey is also the transform that")
    print("  OOMs on a hot key, because one key's entire value list must fit on one")
    print("  worker. A Combine never materialises that list at all.")


# ------------------------------------------------------------ 4. the joins
def section_joins(rows: list[dict]) -> None:
    rule("4. CoGroupByKey vs SIDE INPUT - two ways to join")

    with STATIONS.open(newline="", encoding="utf-8") as fh:
        stations = [(r["station_id"], r["name"]) for r in csv.DictReader(fh)]

    trips = [(r["start_station"], float(r["duration_min"])) for r in rows[:20000]]

    with beam.Pipeline(options=opts()) as p:
        t = p | "T" >> beam.Create(trips)
        s = p | "S" >> beam.Create(stations)
        ({"trips": t, "name": s}
         | beam.CoGroupByKey()
         | "CoOut" >> counter_map("cogbk_groups"))
    cogbk = read_counters(p).get("cogbk_groups", 0)

    with beam.Pipeline(options=opts()) as p2:
        lookup = p2 | "L" >> beam.Create(stations)
        side = beam.pvalue.AsDict(lookup)
        t2 = p2 | "T2" >> beam.Create(trips)
        (t2
         | beam.Map(lambda kv, d: (d.get(kv[0], "?"), kv[1]), side)
         | beam.combiners.Count.PerKey()
         | "SideOut" >> counter_map("side_groups"))
    side_n = read_counters(p2).get("side_groups", 0)

    print(f"  CoGroupByKey : {len(trips):,} trips joined to {len(stations)} stations")
    print(f"                 -> {cogbk} groups. BOTH sides were shuffled by key.")
    print(f"  Side input   : the same join -> {side_n} groups, small side BROADCAST")
    print("                 into every worker. The big side never moved.\n")
    print("  The rule the exam tests: when one side fits in worker memory, a side input")
    print("  avoids shuffling the large side entirely. When BOTH sides are large you")
    print("  have no choice - CoGroupByKey. And a side input that does NOT fit is how")
    print("  you OOM every worker simultaneously rather than just one.")


# ------------------------------------------------------ 5. Flatten/Partition
def section_flatten_partition(rows: list[dict]) -> None:
    rule("5. FLATTEN and PARTITION - union and split")
    sample = rows[:9000]
    electric = [r for r in sample if r["bike_type"] == "electric"]
    classic = [r for r in sample if r["bike_type"] == "classic"]

    def bucket(row, n):
        m = float(row["duration_min"])
        return 0 if m < 10 else (1 if m < 25 else 2)

    with beam.Pipeline(options=opts()) as p:
        e = p | "E" >> beam.Create(electric)
        c = p | "C" >> beam.Create(classic)
        allrows = (e, c) | beam.Flatten()
        allrows | "M" >> counter_map("flatten_out")
        short, mid, long_ = allrows | beam.Partition(bucket, 3)
        short | "P0" >> counter_map("part_short")
        mid | "P1" >> counter_map("part_mid")
        long_ | "P2" >> counter_map("part_long")

    c = read_counters(p)
    parts = (c.get("part_short", 0), c.get("part_mid", 0), c.get("part_long", 0))

    print(f"  Flatten   : {len(electric):,} electric + {len(classic):,} classic "
          f"= {c.get('flatten_out', 0):,}")
    print("              a UNION - no grouping, no dedup, no key required, and every")
    print("              input PCollection must share the same element type.")
    print(f"  Partition : {parts[0]:,} short / {parts[1]:,} mid / {parts[2]:,} long")
    print(f"              {sum(parts):,} total - Partition is EXHAUSTIVE and DISJOINT,")
    print("              which is exactly what separates it from three Filters.")


# ------------------------------------------------------------- 6. hot key
def section_hot_key(rows: list[dict]) -> None:
    rule("6. THE HOT KEY - and with_hot_key_fanout")
    base = [(r["start_station"], float(r["duration_min"])) for r in rows]
    hot = [("ST01", float(r["duration_min"])) for r in rows[:30000]]
    skewed = base + hot

    counts: dict[str, int] = {}
    for k, _ in skewed:
        counts[k] = counts.get(k, 0) + 1
    biggest = max(counts.values())
    median = sorted(counts.values())[len(counts) // 2]

    def checksum(kv):
        # An integer fingerprint of the result, so the two plans can be compared.
        return int(round(kv[1] * 1000))

    with beam.Pipeline(options=opts()) as p:
        src = p | beam.Create(skewed)
        (src
         | "Plain" >> beam.CombinePerKey(beam.combiners.MeanCombineFn())
         | "PlainSum" >> beam.Map(checksum)
         | "PlainG" >> beam.CombineGlobally(sum)
         | "PlainOut" >> beam.Map(
             lambda v: Metrics.counter(NS, "plain_checksum").inc(v)))
        (src
         | "Fanout" >> beam.CombinePerKey(beam.combiners.MeanCombineFn())
                           .with_hot_key_fanout(lambda k: 16 if k == "ST01" else 1)
         | "FanSum" >> beam.Map(checksum)
         | "FanG" >> beam.CombineGlobally(sum)
         | "FanOut" >> beam.Map(
             lambda v: Metrics.counter(NS, "fanout_checksum").inc(v)))

    c = read_counters(p)
    plain_ck, fan_ck = c.get("plain_checksum", 0), c.get("fanout_checksum", 0)

    print(f"  Skew: hottest key {biggest:,} records vs median {median:,}"
          f"  ->  {biggest / median:.1f}x")
    print(f"  Plain CombinePerKey checksum : {plain_ck:,}")
    print(f"  with_hot_key_fanout checksum : {fan_ck:,}")
    print(f"  Identical results            : {plain_ck == fan_ck}")
    print("\n  Fanout inserts an intermediate combine for the named key, so the hot key")
    print("  is pre-reduced by 16 parallel shards before a final merge. It changes the")
    print("  PLAN, never the answer. It cannot help GroupByKey - only a Combine can be")
    print("  split into partial aggregations, which is the whole reason it works.")


# ---------------------------------------------------------------- 7. fusion
def section_fusion(rows: list[dict]) -> None:
    rule("7. FUSION - the optimisation you sometimes have to break")
    seeds = rows[:200]

    class Explode(beam.DoFn):
        def __init__(self):
            self.out = Metrics.counter(NS, "fanned_out")

        def process(self, row):
            for i in range(200):
                self.out.inc()
                yield (row["start_station"], i)

    with beam.Pipeline(options=opts()) as p:
        (p | beam.Create(seeds)
           | beam.ParDo(Explode())
           | beam.Reshuffle()                     # <-- the fusion break
           | beam.combiners.Count.PerKey()
           | "FuseOut" >> counter_map("fusion_keys"))

    c = read_counters(p)
    print(f"  {len(seeds)} input elements -> {c.get('fanned_out', 0):,} elements after "
          f"the high-fan-out ParDo.")
    print("\n  Dataflow FUSES consecutive steps so intermediate results are never")
    print("  materialised. Usually that is free speed. It hurts in two shapes:")
    print("    a) HIGH FAN-OUT   - parallelism is capped at the INPUT count (200 here),")
    print("                        so 40,000 downstream elements get 200 threads")
    print("    b) NON-SPLITTABLE - one gzipped file fuses into a single thread, and")
    print("                        the job will not scale no matter the worker count")
    print("\n  Reshuffle() breaks the fusion by forcing a materialisation point, after")
    print("  which the downstream stage is re-parallelised. On DirectRunner this is a")
    print("  no-op for speed - the lesson is the SHAPE, not the local timing.")


def main() -> None:
    if not TRIPS.exists():
        raise SystemExit("Run: python 00_setup/make_data.py")

    print("DATAFLOW BATCH PROCESSING - bounded data and the machinery around it")
    rows = section_bounded()
    section_dlq(rows)
    section_grouping(rows)
    section_joins(rows)
    section_flatten_partition(rows)
    section_hot_key(rows)
    section_fusion(rows)

    rule("WHAT THE MANAGED SERVICE ADDS THAT A LOCAL RUNNER CANNOT SHOW")
    print("""  Everything above is pipeline SEMANTICS, and they are identical on Dataflow.
  The four below are properties of the managed service. They are documented in
  the README rather than demonstrated here, because there is no honest local
  proxy for any of them:

    Dynamic work rebalancing   a straggler's unprocessed work is split and
                               handed to idle workers. It cannot split ONE
                               record, which is why a hot record still stalls.
    Dataflow Shuffle           grouping/joining moves off worker disks onto the
                               service backend, removing the usual OOM and disk
                               I/O bottleneck for large batch aggregations.
    FlexRS                     preemptible + regular VM mix, queued for up to
                               six hours, for batch that is not time-critical.
                               REQUIRES service-side shuffle to survive a
                               preemption without losing intermediate results.
    Autoscaling                --num_workers sets the start, --max_num_workers
                               the cap. Hot keys and non-splittable sources
                               both defeat it.

  A script claiming to measure those on one laptop would be theatre.""")


if __name__ == "__main__":
    main()
