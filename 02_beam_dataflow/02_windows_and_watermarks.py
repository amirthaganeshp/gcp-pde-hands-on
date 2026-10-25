"""Event time, windowing, watermarks, triggers and late data.

This is the hardest part of Dataflow to hold in your head and the
easiest to SEE once you can run it. Every number below is measured on
the synthetic trip stream, which was generated with a deliberate
event-time/processing-time gap: ~8% of events arrive minutes late
rather than seconds.

  1. Event time vs processing time - the same data, two answers
  2. Fixed (tumbling) windows
  3. Sliding (hopping) windows - one element, several windows
  4. Session windows - the gap decides everything
  5. Watermarks, triggers and ALLOWED LATENESS, with TestStream

EXECUTED IN FULL on a local runner. Sections 1-4 are batch pipelines
over the real dataset; section 5 uses Beam's TestStream so the watermark
can be advanced deliberately rather than waited for.

Run:
    python 00_setup/make_data.py            # once
    python 02_beam_dataflow/02_windows_and_watermarks.py

Guide reference: Success Guide pp. 80-87 (windowing, triggers,
watermarks); Ultimate Edition section 2.4.
"""

from __future__ import annotations

import csv
import io
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

for _noisy in ("apache_beam.utils.subprocess_server", "PrismRunner",
               "apache_beam.runners.portability.prism_runner",
               "apache_beam.runners.portability.fn_api_runner.fn_runner"):
    logging.getLogger(_noisy).setLevel(logging.ERROR)

import apache_beam as beam  # noqa: E402
from apache_beam.options.pipeline_options import (  # noqa: E402
    PipelineOptions, StandardOptions)
from apache_beam.transforms import window  # noqa: E402
from apache_beam.transforms.trigger import (  # noqa: E402
    AccumulationMode, AfterCount, AfterWatermark)

REPO = Path(__file__).resolve().parent.parent
TRIPS = REPO / "data" / "trips.csv"

FIELDS = ["trip_id", "event_time", "processing_time", "lag_seconds",
          "start_station", "end_station", "bike_type", "duration_min",
          "distance_km", "member"]

HOUR = 3600


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


def to_epoch(iso: str) -> float:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp()


def parse(line: str) -> dict:
    row = next(csv.reader(io.StringIO(line)))
    d = dict(zip(FIELDS, row))
    d["event_epoch"] = to_epoch(d["event_time"])
    d["proc_epoch"] = to_epoch(d["processing_time"])
    d["lag_seconds"] = float(d["lag_seconds"])
    return d


def read_trips(p):
    return (p
            | "Read" >> beam.io.ReadFromText(str(TRIPS), skip_header_lines=1)
            | "Parse" >> beam.Map(parse))


class KeyByWindow(beam.DoFn):
    """Emit (window_start, 1) so windows can be counted outside the pipeline."""

    def process(self, element, win=beam.DoFn.WindowParam):
        yield (int(win.start), 1)


OUT = REPO / "outputs"


def sink(pcoll, name: str):
    """Write a PCollection to a single file under outputs/.

    WHY NOT JUST APPEND TO A LIST IN A CLOSURE:
    an earlier version of this file did, and every measurement came back
    EMPTY. Beam executes DoFns in worker processes - on this runner, a
    separate OS process - so mutating a Python list inside the pipeline
    changes a copy that the main process never sees. The pipeline
    reported success and every count was zero.

    This is not a local-runner quirk to be worked around; it is how
    distributed execution works, and the same code on Dataflow would
    fail the same way across machines. Results leave a pipeline through
    a SINK, never through a variable.
    """
    return pcoll | f"Write{name}" >> beam.io.WriteToText(
        str(OUT / name), shard_name_template="")


def read_sink(name: str) -> list[str]:
    path = OUT / name
    if not path.exists():
        return []
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln]


def read_pairs(name: str) -> dict[int, int]:
    """Read back lines written as 'window_start,count'."""
    out: dict[int, int] = {}
    for ln in read_sink(name):
        k, v = ln.split(",")
        out[int(k)] = int(v)
    return out


# ==================================== 1. event vs processing time
def event_vs_processing() -> dict:
    banner("1. Event time vs processing time - the same data, two answers")

    with beam.Pipeline(options=PipelineOptions(runner="DirectRunner")) as p:
        trips = read_trips(p)

        # Window by EVENT time - when the trip actually happened.
        ev_out = (trips
                  | "StampEvent" >> beam.Map(
                      lambda t: window.TimestampedValue(t, t["event_epoch"]))
                  | "WinEvent" >> beam.WindowInto(window.FixedWindows(HOUR))
                  | "KeyEvent" >> beam.ParDo(KeyByWindow())
                  | "GroupEvent" >> beam.GroupByKey()
                  | "FmtEvent" >> beam.MapTuple(
                      lambda k, v: f"{k},{sum(v)}"))
        sink(ev_out, "win_event")

        # Window by PROCESSING time - when the record turned up.
        pr_out = (trips
                  | "StampProc" >> beam.Map(
                      lambda t: window.TimestampedValue(t, t["proc_epoch"]))
                  | "WinProc" >> beam.WindowInto(window.FixedWindows(HOUR))
                  | "KeyProc" >> beam.ParDo(KeyByWindow())
                  | "GroupProc" >> beam.GroupByKey()
                  | "FmtProc" >> beam.MapTuple(
                      lambda k, v: f"{k},{sum(v)}"))
        sink(pr_out, "win_proc")

    ev = read_pairs("win_event")
    pr = read_pairs("win_proc")
    shared = sorted(set(ev) & set(pr))

    moved = sum(abs(ev.get(w, 0) - pr.get(w, 0)) for w in set(ev) | set(pr)) // 2
    total = sum(ev.values())

    print(f"  {total:,} trips, bucketed into 1-hour windows two ways.\n")
    print(f"  {'window start (UTC)':<22} {'by event time':>14} "
          f"{'by processing time':>19}")
    print("  " + "-" * 60)
    for w in shared[:6]:
        stamp = datetime.fromtimestamp(w, timezone.utc).strftime("%m-%d %H:%M")
        print(f"  {stamp:<22} {ev.get(w, 0):>14,} {pr.get(w, 0):>19,}")

    print(f"\n  windows by event time      : {len(ev)}")
    print(f"  windows by processing time : {len(pr)}")
    print(f"  ** {moved:,} trips ({moved / total:.1%}) fall in a DIFFERENT "
          f"hour **")

    print("\n  Same data, same window size, two different answers. A trip at")
    print("  08:59 that arrives at 09:04 is an 08:00 trip by event time and a")
    print("  09:00 trip by processing time.")
    print("\n  **Event time is almost always the one you want**, because it is")
    print("  a property of the world; processing time is a property of your")
    print("  infrastructure, and it changes if a job is slow, retried or")
    print("  backfilled. Re-running a processing-time pipeline over old data")
    print("  puts everything in one window - which is the classic backfill")
    print("  bug, and it is silent.")
    return {"total": total, "moved": moved,
            "n_event": len(ev), "n_proc": len(pr)}


# ==================================== 2-3. fixed and sliding
def fixed_and_sliding() -> dict:
    banner("2-3. Fixed (tumbling) vs sliding (hopping) windows")

    with beam.Pipeline(options=PipelineOptions(runner="DirectRunner")) as p:
        stamped = (read_trips(p)
                   | "Stamp" >> beam.Map(
                       lambda t: window.TimestampedValue(t, t["event_epoch"])))

        f_out = (stamped
                 | "Fixed" >> beam.WindowInto(window.FixedWindows(HOUR))
                 | "KeyF" >> beam.ParDo(KeyByWindow())
                 | "GroupF" >> beam.GroupByKey()
                 | "FmtF" >> beam.MapTuple(lambda k, v: f"{k},{sum(v)}"))
        sink(f_out, "win_fixed")

        # 1-hour window every 30 minutes: each element lands in TWO.
        s_out = (stamped
                 | "Sliding" >> beam.WindowInto(
                     window.SlidingWindows(HOUR, HOUR // 2))
                 | "KeyS" >> beam.ParDo(KeyByWindow())
                 | "GroupS" >> beam.GroupByKey()
                 | "FmtS" >> beam.MapTuple(lambda k, v: f"{k},{sum(v)}"))
        sink(s_out, "win_sliding")

    fixed = read_pairs("win_fixed")
    sliding = read_pairs("win_sliding")
    n_fixed = sum(fixed.values())
    n_sliding = sum(sliding.values())

    print(f"  {'':<12} {'windows':>9} {'element-window pairs':>22}")
    print("  " + "-" * 48)
    print(f"  {'fixed 1h':<12} {len(fixed):>9} {n_fixed:>22,}")
    print(f"  {'sliding 1h/30m':<12} {len(sliding):>9} {n_sliding:>22,}")
    print(f"\n  ratio: {n_sliding / n_fixed:.2f}x  "
          f"(period {HOUR}s / hop {HOUR // 2}s = "
          f"{HOUR // (HOUR // 2)} overlapping windows)")

    print("\n  **Fixed windows partition time; sliding windows cover it more")
    print("  than once.** Each element belongs to exactly one fixed window,")
    print("  and to size/period sliding windows - here 2.")
    print("\n  That multiple is a real cost: state, shuffle and output all")
    print("  scale with it. A 24-hour window hopping every 5 minutes puts")
    print("  every element in 288 windows. Sliding windows are for rolling")
    print("  metrics ('trips in the last hour, updated every 30 min'), not")
    print("  for a default.")
    return {"n_fixed_windows": len(fixed), "n_sliding_windows": len(sliding),
            "pairs_fixed": n_fixed, "pairs_sliding": n_sliding}


# ==================================== 4. sessions
def sessions() -> dict:
    banner("4. Session windows - the gap decides everything")

    results: dict[int, int] = {}

    for gap_min in (5, 15, 60):
        name = f"sessions_{gap_min}"
        with beam.Pipeline(options=PipelineOptions(runner="DirectRunner")) as p:
            out = (read_trips(p)
                   | "Stamp" >> beam.Map(
                       lambda t: window.TimestampedValue(t, t["event_epoch"]))
                   | "ByStation" >> beam.Map(lambda t: (t["start_station"], 1))
                   | "Sessions" >> beam.WindowInto(
                       window.Sessions(gap_min * 60))
                   | "Group" >> beam.GroupByKey()
                   | "Fmt" >> beam.MapTuple(lambda k, v: f"{k},{sum(v)}"))
            sink(out, name)

        results[gap_min] = len(read_sink(name))

    print(f"  Sessions keyed by start station, over the same 50,000 trips.\n")
    print(f"  {'gap':<10} {'sessions':>10}   note")
    print("  " + "-" * 52)
    prev = None
    for gap, n in results.items():
        note = "" if prev is None else f"{prev / n:.1f}x fewer than above"
        print(f"  {gap:>3} min   {n:>10,}   {note}")
        prev = n

    print("\n  **A session window has no fixed size.** It opens on an element")
    print("  and closes after the gap passes with no further element for that")
    print("  key - so its length is a property of the DATA, not a setting.")
    print("\n  The gap is therefore the whole design decision. Too small and")
    print("  one real period of activity shatters into many sessions; too")
    print("  large and separate visits merge into one. There is no default")
    print("  that is right - it comes from the behaviour being modelled.")
    print("\n  Sessions are also per key. Two stations busy at the same time")
    print("  are two sessions, never one.")
    return results


# ==================================== 5. watermarks and lateness
def watermarks_and_lateness() -> dict:
    banner("5. Watermarks, triggers and ALLOWED LATENESS")

    from apache_beam.testing.test_stream import TestStream

    base = 1_780_000_000          # an arbitrary fixed epoch second
    outcomes: dict[str, list] = {}

    from apache_beam.metrics import Metrics, MetricsFilter
    from apache_beam.utils.windowed_value import PaneInfoTiming

    class CountPanes(beam.DoFn):
        """Report pane counts through METRICS, not a file.

        Section 1-4 write to a sink, but WriteToText cannot finalise in
        STREAMING mode - it leaves several temp shards and the finaliser
        demands a singleton. Metrics work in both modes and on every
        runner, which is why the first Beam file uses them too.
        """

        def __init__(self, ns: str):
            self.panes = Metrics.counter(ns, "panes")
            self.late_panes = Metrics.counter(ns, "late_panes")
            self.pane_size = Metrics.distribution(ns, "pane_size")

        def process(self, kv, pane=beam.DoFn.PaneInfoParam):
            _, values = kv
            n = len(list(values))
            self.panes.inc()
            self.pane_size.update(n)
            if pane.timing == PaneInfoTiming.LATE:
                self.late_panes.inc()
            yield n

    def run(label: str, allowed_lateness: int) -> dict:
        ns = f"lateness_{label}"
        opts = PipelineOptions(runner="DirectRunner")
        opts.view_as(StandardOptions).streaming = True

        # TestStream lets the WATERMARK be advanced deliberately. In a
        # real pipeline the runner infers it from the source and you
        # cannot script it - which is why this is the only honest way to
        # demonstrate late data in a file that must finish.
        stream = (TestStream()
                  .advance_watermark_to(base)
                  # three on-time elements inside the 00:00-00:10 window
                  .add_elements([
                      window.TimestampedValue("on-time-1", base + 10),
                      window.TimestampedValue("on-time-2", base + 20),
                      window.TimestampedValue("on-time-3", base + 30)])
                  # watermark passes the end of the window: it is complete
                  .advance_watermark_to(base + 600)
                  # ...and NOW a straggler for that window turns up
                  .add_elements([
                      window.TimestampedValue("LATE-1", base + 40)])
                  .advance_watermark_to(base + 900)
                  .add_elements([
                      window.TimestampedValue("LATE-2", base + 50)])
                  .advance_watermark_to_infinity())

        with beam.Pipeline(options=opts) as p:
            (p
             | label >> stream
             | "Win" >> beam.WindowInto(
                 window.FixedWindows(600),
                 trigger=AfterWatermark(late=AfterCount(1)),
                 allowed_lateness=allowed_lateness,
                 accumulation_mode=AccumulationMode.ACCUMULATING)
             | "Key" >> beam.Map(lambda e: (0, e))
             | "Group" >> beam.GroupByKey()
             | "Count" >> beam.ParDo(CountPanes(ns)))

        res = p.result

        def counter(name: str) -> int:
            q = res.metrics().query(MetricsFilter().with_name(name))
            return q["counters"][0].result if q["counters"] else 0

        q = res.metrics().query(MetricsFilter().with_name("pane_size"))
        biggest = q["distributions"][0].result.max if q["distributions"] else 0

        return {"panes": counter("panes"),
                "late_panes": counter("late_panes"),
                "max_pane": biggest}

    outcomes["none"] = run("NoLateness", 0)
    outcomes["generous"] = run("WithLateness", 3600)

    print(f"  Three on-time elements land in a 10-minute window. The")
    print(f"  watermark then passes the window's end, and TWO stragglers")
    print(f"  for that window arrive afterwards.\n")
    print(f"  {'allowed_lateness':<20} {'panes':>7} {'late panes':>12} "
          f"{'largest pane':>14}")
    print("  " + "-" * 58)
    for label, allowed in (("none", "0 s"), ("generous", "3600 s")):
        o = outcomes[label]
        print(f"  {allowed:<20} {o['panes']:>7} {o['late_panes']:>12} "
              f"{o['max_pane']:>14}")

    dropped = outcomes["generous"]["max_pane"] - outcomes["none"]["max_pane"]

    print("\n  ** A NEGATIVE RESULT, reported rather than hidden. **")
    print("  Both rows are identical: the on-time pane fired correctly, but")
    print("  NO late pane fired and the stragglers were dropped even with")
    print("  allowed_lateness = 3600. That is not the trigger being wrong -")
    print("  it was checked against three runners:")
    print("      DirectRunner (-> Prism)    same result at both settings")
    print("      BundleBasedDirectRunner    same result at both settings")
    print("      FnApiRunner                NotImplementedError: TestStream")
    print("\n  So **late-pane firing does not reproduce on the local runners")
    print("  available here.** The on-time half is real; treat the late half")
    print("  as unverified locally and confirm it on Dataflow if you depend")
    print("  on it. Section 5b measures the exposure a different way, on")
    print("  data rather than on a runner's trigger implementation.")

    print("\n  **The watermark is the runner's estimate that no more data")
    print("  will arrive for a window.** When it passes the window's end, the")
    print("  window fires - that is the on-time pane.")
    print("\n  Anything arriving afterwards is LATE, and what happens to it is")
    print("  entirely `allowed_lateness`:")
    print("    allowed_lateness = 0      the window's state is discarded")
    print("                              immediately and late data is DROPPED")
    print("                              silently - no error, no log, no metric")
    print("                              unless you add one")
    print("    allowed_lateness > 0      state is kept that much longer, the")
    print("                              late trigger fires again, and the")
    print("                              result is corrected")
    print(f"\n  Measured here: {dropped} element(s) survived with lateness")
    print("  allowed that were dropped without it.")

    print("\n  The cost is state. `allowed_lateness` is how long every window")
    print("  is held in memory after it should have closed, so a day of")
    print("  lateness across millions of keys is a real bill - and the usual")
    print("  cause of a streaming job whose memory grows without bound.")

    print("\n  ACCUMULATING vs DISCARDING decides what a late pane contains:")
    print("    ACCUMULATING  the complete corrected answer - use it when the")
    print("                  sink overwrites, e.g. upserting into BigQuery")
    print("    DISCARDING    only what is new since the last pane - use it")
    print("                  when the sink adds, and you will sum downstream")
    print("\n  Choosing wrong double-counts or under-counts, and both look")
    print("  perfectly plausible in a dashboard.")

    return {"panes_none": outcomes["none"]["panes"],
            "panes_generous": outcomes["generous"]["panes"],
            "rescued": dropped}


# ==================================== 5b. lateness, measured on real data
def lateness_on_real_data() -> dict:
    """How much of the real stream would a given allowed_lateness save?

    Section 5 could not demonstrate late firing on a local runner. This
    measures the same question from the other end - not "does the
    trigger fire" but "how much data is at stake" - using the actual
    event-time/processing-time gap in the dataset.

    An element is LATE for a window if it arrives after that window has
    closed: proc_time > window_end. That is the definition
    `allowed_lateness` is measured against.
    """
    banner("5b. How much is at stake - measured on the real stream")

    rows = []
    with TRIPS.open(encoding="utf-8") as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            d = dict(zip(FIELDS, row))
            rows.append((to_epoch(d["event_time"]),
                         to_epoch(d["processing_time"])))

    total = len(rows)
    print(f"  {total:,} trips, using their real event and processing times.\n")
    print(f"  {'window':<10} {'late events':>12} {'% late':>9}   "
          f"{'lateness to keep 99%':>22}")
    print("  " + "-" * 62)

    out: dict[str, float] = {}
    for label, w in (("1 min", 60), ("10 min", 600), ("1 hour", 3600)):
        overshoot = []
        for ev, pr in rows:
            win_end = (ev // w) * w + w
            if pr > win_end:
                overshoot.append(pr - win_end)
        n_late = len(overshoot)
        p99 = sorted(overshoot)[int(len(overshoot) * 0.99)] if overshoot else 0
        out[label] = n_late / total
        print(f"  {label:<10} {n_late:>12,} {n_late / total:>8.1%}   "
              f"{p99:>19,.0f} s")

    print("\n  **The window size decides how much data is late**, not just the")
    print("  network. A one-minute window turns a modest processing lag into")
    print("  a large late fraction; the same stream in one-hour windows is")
    print("  almost all on time.")
    print("\n  So `allowed_lateness` is not a property of your data alone - it")
    print("  is a property of your data AND your window size, and the two")
    print("  have to be chosen together.")
    print("\n  The right-hand column is the setting that would retain 99% of")
    print("  the stragglers. Anything less is data you are choosing to drop;")
    print("  anything more is window state you are choosing to pay for.")
    return out


def main() -> None:
    if not TRIPS.exists():
        raise SystemExit(f"  {TRIPS} not found - run 00_setup/make_data.py first.")

    print("=" * 72)
    print("  EVENT TIME, WINDOWS, WATERMARKS AND LATE DATA".center(72))
    print("=" * 72)

    a = event_vs_processing()
    b = fixed_and_sliding()
    c = sessions()
    d = watermarks_and_lateness()
    e = lateness_on_real_data()

    banner("Summary - all measured")
    print(f"  - {a['moved']:,} of {a['total']:,} trips "
          f"({a['moved'] / a['total']:.1%}) land in a different hour "
          f"depending on which clock you window by")
    print(f"  - sliding 1h/30m produced {b['pairs_sliding'] / b['pairs_fixed']:.2f}x "
          f"the element-window pairs of fixed 1h")
    print(f"  - session count by gap: "
          f"{ {f'{k}min': v for k, v in c.items()} }")
    print(f"  - late fraction by window size: "
          f"{ {k: f'{v:.1%}' for k, v in e.items()} }")
    print(f"  - late-pane firing did NOT reproduce on any local runner "
          f"(see section 5)")
    print("\n  Event time is a property of the world; processing time is a")
    print("  property of your infrastructure. Window by the former, and")
    print("  decide deliberately what to do about the stragglers - because")
    print("  the default is to drop them without telling you.")


if __name__ == "__main__":
    main()
