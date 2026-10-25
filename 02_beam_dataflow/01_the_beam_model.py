"""The Beam model: the transforms every Dataflow pipeline is built from.

Dataflow does not have its own programming model - it runs Apache Beam.
So "learning Dataflow" is mostly learning Beam, and the DirectRunner used
here executes the SAME pipeline code Dataflow would, on this machine, for
free. Only the runner changes.

  1. A pipeline is a DAG of PTransforms over PCollections
  2. The element-wise transforms - Map, FlatMap, Filter
  3. GROUPING, and the difference that decides pipeline cost
  4. Side inputs - the small-table join
  5. Branching: one PCollection, several outputs
  6. What the runner did, from Beam's own metrics

EXECUTED IN FULL. Every number printed was measured on the DirectRunner.

Run:
    python 00_setup/make_data.py            # once
    python 02_beam_dataflow/01_the_beam_model.py

Guide reference: Success Guide pp. 73-79 (the Apache Beam model).
"""

from __future__ import annotations

import csv
import io
import logging
import time
from pathlib import Path

# Beam narrates its own service startup at WARNING level, which drowns the
# output this file is actually about. The pipeline is unaffected.
for _noisy in ("apache_beam.utils.subprocess_server", "PrismRunner",
               "apache_beam.runners.portability.prism_runner"):
    logging.getLogger(_noisy).setLevel(logging.ERROR)

import apache_beam as beam
from apache_beam.metrics import Metrics
from apache_beam.options.pipeline_options import PipelineOptions

REPO = Path(__file__).resolve().parent.parent
TRIPS = REPO / "data" / "trips.csv"
STATIONS = REPO / "data" / "stations.csv"

FIELDS = ["trip_id", "event_time", "processing_time", "lag_seconds",
          "start_station", "end_station", "bike_type", "duration_min",
          "distance_km", "member"]


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


def parse_trip(line: str) -> dict:
    row = next(csv.reader(io.StringIO(line)))
    d = dict(zip(FIELDS, row))
    d["duration_min"] = float(d["duration_min"])
    d["distance_km"] = float(d["distance_km"])
    d["member"] = d["member"] == "True"
    return d


# ============================================ counted DoFns
class CountingMap(beam.DoFn):
    """A DoFn that reports how many elements passed through it.

    Beam metrics are the only honest way to answer "how much data crossed
    this step", which is what section 3 needs - and on Dataflow these are
    exactly the counters the job UI shows you.
    """

    def __init__(self, namespace: str, name: str):
        self.counter = Metrics.counter(namespace, name)

    def process(self, element):
        self.counter.inc()
        yield element


def count_of(result, name: str) -> int:
    q = result.metrics().query(
        beam.metrics.MetricsFilter().with_name(name))
    return q["counters"][0].result if q["counters"] else 0


# ============================================ 1. the model
def explain_model() -> None:
    banner("1. PCollections and PTransforms")

    print("  Three nouns, and everything else is detail:")
    print("      Pipeline     the whole DAG")
    print("      PCollection  a distributed, immutable dataset")
    print("      PTransform   an operation producing a new PCollection")

    print("\n  A PCollection is IMMUTABLE. A transform never edits one; it")
    print("  returns a new one. That is why the same PCollection can feed")
    print("  several branches with no interference - see section 5 - and it")
    print("  is what lets the runner retry a failed bundle safely.")

    print("\n  The `|` operator is just 'apply'. `a | b | c` reads left to")
    print("  right and builds a graph, it does NOT execute anything. The")
    print("  pipeline runs when the `with` block exits.")

    print("\n  SAME CODE, DIFFERENT RUNNER. This file asks for DirectRunner")
    print("  on a laptop. Swapping to Dataflow is an options change, not a")
    print("  rewrite - which is the whole argument for Beam and the reason")
    print("  this repository can teach Dataflow without a project:")
    print("      DirectRunner       here, free, single machine")
    print("      DataflowRunner     managed, autoscaled, billed")
    print("      FlinkRunner / SparkRunner   portability, rarely on GCP")

    # Worth checking rather than assuming - see below.
    p = beam.Pipeline(options=PipelineOptions(runner="DirectRunner"))
    actual = type(p.runner)
    print(f"\n  BUT 'DirectRunner' IS NOT ONE RUNNER. Asking for it here gives:")
    print(f"      {actual.__module__}.{actual.__name__}")
    print("  ...a facade that INSPECTS THE PIPELINE and delegates. On Beam")
    print(f"  {beam.__version__} this pipeline is handed to the Prism runner,")
    print("  a portable local runner, not to the old in-process one. Force")
    print("  the legacy path with runner='BundleBasedDirectRunner'.")
    print("\n  It matters because local behaviour is then not a fixed thing:")
    print("  which backend you get depends on your Beam version and on what")
    print("  your pipeline uses. If a pipeline passes locally and fails on")
    print("  Dataflow, 'it worked on DirectRunner' does not narrow it down")
    print("  as much as it sounds like it does.")


# ============================================ 2-6. one pipeline
def run_pipeline() -> dict:
    banner("2-6. One pipeline, measured")

    out_dir = REPO / "outputs"
    out_dir.mkdir(exist_ok=True)
    started = time.perf_counter()

    with beam.Pipeline(options=PipelineOptions(runner="DirectRunner")) as p:

        trips = (
            p
            | "Read" >> beam.io.ReadFromText(str(TRIPS), skip_header_lines=1)
            | "Parse" >> beam.Map(parse_trip)
            | "CountRead" >> beam.ParDo(CountingMap("model", "rows_read"))
        )

        # --- 2. element-wise -------------------------------------------
        # Filter: 1 element in, 0 or 1 out.
        long_trips = (
            trips
            | "LongOnly" >> beam.Filter(lambda t: t["duration_min"] >= 10)
            | "CountLong" >> beam.ParDo(CountingMap("model", "rows_long"))
        )

        # FlatMap: 1 element in, N out. Each trip touches TWO stations, so
        # this is how you fan one record into several keyed records.
        station_events = (
            trips
            | "ToStationEvents" >> beam.FlatMap(
                lambda t: [(t["start_station"], 1), (t["end_station"], 1)])
            | "CountEvents" >> beam.ParDo(CountingMap("model", "station_events"))
        )

        # --- 3. grouping ------------------------------------------------
        # CombinePerKey pre-aggregates on each worker BEFORE the shuffle
        # (combiner lifting). GroupByKey cannot - it must move every
        # element so the grouping function can see them all.
        combined = (
            station_events
            | "CombinePerKey" >> beam.CombinePerKey(sum)
            | "CountCombined" >> beam.ParDo(CountingMap("model", "after_combine"))
        )

        grouped = (
            station_events
            | "GroupByKey" >> beam.GroupByKey()
            | "SumGroups" >> beam.MapTuple(lambda k, vs: (k, sum(vs)))
            | "CountGrouped" >> beam.ParDo(CountingMap("model", "after_group"))
        )

        # --- 4. side input ---------------------------------------------
        stations = (
            p
            | "ReadStations" >> beam.io.ReadFromText(str(STATIONS),
                                                     skip_header_lines=1)
            | "ParseStations" >> beam.Map(
                lambda line: next(csv.reader(io.StringIO(line))))
            | "ToKV" >> beam.Map(lambda r: (r[0], {"name": r[1],
                                                   "district": r[4]}))
        )

        named = (
            combined
            | "AddNames" >> beam.Map(
                lambda kv, lookup: (lookup.get(kv[0], {}).get("name", "?"),
                                    kv[1]),
                lookup=beam.pvalue.AsDict(stations))
            | "WriteNamed" >> beam.io.WriteToText(
                str(out_dir / "station_totals"), shard_name_template="")
        )

        # --- 5. branching ----------------------------------------------
        # `trips` is consumed by several transforms. Nothing is copied and
        # nothing conflicts, because a PCollection is immutable.
        _ = (
            trips
            | "Members" >> beam.Filter(lambda t: t["member"])
            | "CountMembers" >> beam.ParDo(CountingMap("model", "rows_member"))
        )
        _ = (
            trips
            | "Electric" >> beam.Filter(lambda t: t["bike_type"] == "electric")
            | "CountElectric" >> beam.ParDo(CountingMap("model", "rows_electric"))
        )

    result = p.result
    elapsed = time.perf_counter() - started

    names = ["rows_read", "rows_long", "station_events", "after_combine",
             "after_group", "rows_member", "rows_electric"]
    return {n: count_of(result, n) for n in names} | {"elapsed": elapsed}


def report(m: dict) -> None:
    n = m["rows_read"]

    print(f"\n  Pipeline ran in {m['elapsed']:.1f} s locally "
          f"(DirectRunner -> Prism, see section 1).\n")
    print(f"  {'stage':<26} {'elements':>10}   note")
    print("  " + "-" * 72)
    print(f"  {'rows read':<26} {n:>10,}   the source")
    print(f"  {'after Filter (>=10 min)':<26} {m['rows_long']:>10,}   "
          f"{m['rows_long']/n:.1%} kept - Filter only ever removes")
    print(f"  {'after FlatMap':<26} {m['station_events']:>10,}   "
          f"exactly 2x - one per station touched")
    print(f"  {'members':<26} {m['rows_member']:>10,}   "
          f"{m['rows_member']/n:.1%}")
    print(f"  {'electric bikes':<26} {m['rows_electric']:>10,}   "
          f"{m['rows_electric']/n:.1%}")

    banner("3. The grouping difference - this is the exam point")

    print(f"  Both paths start from the same {m['station_events']:,} keyed")
    print(f"  elements and both produce {m['after_combine']} results, one per")
    print("  station. They are NOT equivalent in cost.\n")
    print(f"  {'transform':<20} {'in':>10} {'out':>10}   what crosses the shuffle")
    print("  " + "-" * 72)
    print(f"  {'CombinePerKey':<20} {m['station_events']:>10,} "
          f"{m['after_combine']:>10}   ~one partial sum per key per worker")
    print(f"  {'GroupByKey':<20} {m['station_events']:>10,} "
          f"{m['after_group']:>10}   EVERY element, ungrouped")

    print("\n  CombinePerKey is associative and commutative, so Beam applies")
    print("  COMBINER LIFTING: each worker folds its own elements down to a")
    print("  partial result first, and only the partials are shuffled. The")
    print("  volume crossing the network drops from one-per-element to")
    print("  roughly one-per-key-per-worker.")
    print("\n  GroupByKey cannot do that. `sum(vs)` needs every value in one")
    print("  place, so every element moves.")

    print("\n  At this scale, on one machine, both finish instantly and a")
    print("  local runner does not really shuffle - so treat the mechanism")
    print("  as the lesson, not the timing. On Dataflow with a hot key and")
    print("  millions of elements this is the difference between a job that")
    print("  finishes and a job that stalls on one straggler worker.")

    print("\n  >> Reach for CombinePerKey, Count, Sum, Mean or a custom")
    print("     CombineFn. Reach for GroupByKey only when you genuinely")
    print("     need to see all the values at once - and expect to pay.")


def closing() -> None:
    banner("4-5. Side inputs and branching, recapped")

    print("  SIDE INPUT - the small-table join. `beam.pvalue.AsDict(stations)`")
    print("  broadcasts the 8-row dimension to every worker, so the join")
    print("  needs no shuffle at all.")
    print("      AsDict / AsList  materialise the whole side input in memory")
    print("      AsSingleton      one value")
    print("  It must be SMALL. A side input is broadcast per worker, so a")
    print("  large one is an out-of-memory error rather than a slow join -")
    print("  for a big-to-big join use CoGroupByKey instead.")

    print("\n  BRANCHING - `trips` fed five separate transforms above. No")
    print("  copy, no conflict, because a PCollection is immutable. The")
    print("  source is read once and the runner fuses what it can.")

    print("\n  Output written to outputs/station_totals.")


def main() -> None:
    if not TRIPS.exists():
        raise SystemExit(f"  {TRIPS} not found - run 00_setup/make_data.py first.")

    print("=" * 72)
    print("  THE BEAM MODEL - what Dataflow actually runs".center(72))
    print("=" * 72)

    explain_model()
    metrics = run_pipeline()
    report(metrics)
    closing()

    banner("Summary")
    print("  - Dataflow runs Beam; a local runner runs the same code free.")
    print("  - 'DirectRunner' is a facade that picks a backend - here Prism.")
    print("  - A PCollection is immutable, which is what makes branching")
    print("    and retries safe.")
    print("  - Filter removes, Map is 1:1, FlatMap is 1:N.")
    print("  - CombinePerKey lifts the combine before the shuffle;")
    print("    GroupByKey moves every element. Same answer, different bill.")
    print("  - Side inputs are broadcast, so they must stay small.")


if __name__ == "__main__":
    main()
