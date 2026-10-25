"""Why your alert pages at 3am: thresholds against seasonal data.

Cloud Monitoring will happily alert on any metric you point it at. The
hard part is not configuring the alert - it is choosing a condition that
fires when something is wrong and stays quiet when nothing is.

A static threshold on a metric with daily seasonality cannot do both,
and this file measures why using the real hourly pattern in the trip
data.

  1. The metric - real seasonality, not noise
  2. A static threshold, and what it costs you
  3. Seasonal baselines - comparing like with like
  4. DURATION windows - the cheapest fix there is
  5. Metric types, and which alert belongs on which

EXECUTED IN FULL. Pure Python over the trip data.

Run:
    python 00_setup/make_data.py       # once
    python 11_ops_cost_monitoring/02_monitoring/alerting_thresholds.py

Guide reference: Success Guide pp. 115-117; Ultimate Edition section 5.4.
"""

from __future__ import annotations

import csv
import random
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRIPS = REPO / "data" / "trips.csv"

SEED = 42
N_INCIDENTS = 4          # genuine anomalies injected


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


def hourly_series() -> list[tuple[datetime, int]]:
    """Trips per hour - a metric with real daily and weekly shape."""
    buckets: dict[str, int] = defaultdict(int)
    with TRIPS.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            buckets[r["event_time"][:13]] += 1
    return sorted((datetime.fromisoformat(k + ":00:00"), v)
                  for k, v in buckets.items())


def inject_incidents(series, rng):
    """Add genuine outages - a real drop, at a random hour."""
    series = list(series)
    incident_idx = rng.sample(range(24, len(series) - 1), N_INCIDENTS)
    for i in incident_idx:
        ts, v = series[i]
        series[i] = (ts, max(0, int(v * 0.15)))     # 85% drop = an outage
    return series, set(incident_idx)


# ============================================ 1. the metric
def describe(series) -> dict:
    banner("1. The metric - real seasonality, not noise")

    values = [v for _, v in series]
    by_hour: dict[int, list[int]] = defaultdict(list)
    for ts, v in series:
        by_hour[ts.hour].append(v)

    peak_h = max(by_hour, key=lambda h: statistics.mean(by_hour[h]))
    trough_h = min(by_hour, key=lambda h: statistics.mean(by_hour[h]))
    peak = statistics.mean(by_hour[peak_h])
    trough = statistics.mean(by_hour[trough_h])

    print(f"  {len(series):,} hourly buckets over {len(series) // 24} days\n")
    print(f"  {'overall mean':<22} {statistics.mean(values):>9.1f}")
    print(f"  {'overall min / max':<22} {min(values):>4} / {max(values)}")
    print(f"  {'busiest hour (mean)':<22} {peak:>9.1f}   at {peak_h:02d}:00")
    print(f"  {'quietest hour (mean)':<22} {trough:>9.1f}   at {trough_h:02d}:00")
    print(f"  {'peak / trough ratio':<22} {peak / max(trough, 1):>9.1f}x")

    print("\n  **That ratio is the problem.** A normal quiet hour and a")
    print("  normal busy hour differ by more than an outage differs from")
    print("  normal - so no single number separates 'quiet' from 'broken'.")
    return {"mean": statistics.mean(values), "peak": peak, "trough": trough,
            "peak_h": peak_h, "trough_h": trough_h}


# ============================================ 2. static threshold
def static_threshold(series, incidents: set) -> dict:
    banner("2. A static threshold - and what it costs")

    values = [v for _, v in series]
    mean = statistics.mean(values)

    print(f"  Alert when trips/hour drops below a fixed number.\n")
    print(f"  {'threshold':>12} {'alerts':>8} {'true':>7} {'FALSE':>7} "
          f"{'missed':>8} {'precision':>11}")
    print("  " + "-" * 60)

    out = {}
    for frac in (0.20, 0.35, 0.50, 0.75):
        thresh = mean * frac
        fired = {i for i, (_, v) in enumerate(series) if v < thresh}
        tp = len(fired & incidents)
        fp = len(fired - incidents)
        fn = len(incidents - fired)
        prec = tp / len(fired) if fired else 0.0
        out[frac] = {"threshold": thresh, "fired": len(fired),
                     "tp": tp, "fp": fp, "fn": fn, "precision": prec}
        print(f"  {thresh:>12.0f} {len(fired):>8} {tp:>7} {fp:>7} "
              f"{fn:>8} {prec:>10.0%}")

    best = max(out, key=lambda k: out[k]["precision"])
    b = out[best]

    print(f"\n  There are only {len(incidents)} real incidents in this data.")
    print(f"  The best static threshold still fires {b['fired']} times at "
          f"{b['precision']:.0%} precision.")

    print("\n  **Every false alert is a page at 3am for a quiet Tuesday")
    print("  night that looked exactly like an outage.** Raise the threshold")
    print("  to stop them and you stop catching daytime incidents, because")
    print("  a daytime outage still leaves more traffic than a healthy")
    print("  night.")

    print("\n  This is not a tuning problem. One number cannot describe a")
    print("  metric whose normal range moves by the hour.")
    return out


# ============================================ 3. seasonal baseline
def seasonal_baseline(series, incidents: set) -> dict:
    banner("3. Compare like with like - a per-hour baseline")

    by_hour: dict[int, list[int]] = defaultdict(list)
    for ts, v in series:
        by_hour[ts.hour].append(v)
    baseline = {h: statistics.median(vs) for h, vs in by_hour.items()}

    print("  Alert when this hour is far below the MEDIAN FOR THAT HOUR.\n")
    print(f"  {'drop vs normal':>15} {'alerts':>8} {'true':>7} {'FALSE':>7} "
          f"{'missed':>8} {'precision':>11}")
    print("  " + "-" * 62)

    out = {}
    for frac in (0.75, 0.50, 0.35, 0.25):
        fired = {i for i, (ts, v) in enumerate(series)
                 if v < baseline[ts.hour] * frac}
        tp = len(fired & incidents)
        fp = len(fired - incidents)
        fn = len(incidents - fired)
        prec = tp / len(fired) if fired else 0.0
        out[frac] = {"fired": len(fired), "tp": tp, "fp": fp,
                     "fn": fn, "precision": prec}
        print(f"  {'below ' + format(frac, '.0%'):>15} {len(fired):>8} "
              f"{tp:>7} {fp:>7} {fn:>8} {prec:>10.0%}")

    best = max(out, key=lambda k: out[k]["precision"])
    b = out[best]
    print(f"\n  Best: fires {b['fired']} times, {b['tp']} true, "
          f"{b['fp']} false - **{b['precision']:.0%} precision**")

    print("\n  Same data, same incidents, same alerting system. The only")
    print("  change is comparing 03:00 against other 03:00s instead of")
    print("  against a global average.")

    print("\n  Cloud Monitoring does this with a **metric-threshold")
    print("  condition on a ratio**, or with forecast/anomaly conditions.")
    print("  The general rule: alert on a metric that is already")
    print("  NORMALISED - error RATE not error count, latency PERCENTILE")
    print("  not mean, freshness LAG not row count.")
    return out


# ============================================ 4. duration
def duration_window(series, incidents: set) -> dict:
    banner("4. Duration windows - the cheapest fix available")

    by_hour: dict[int, list[int]] = defaultdict(list)
    for ts, v in series:
        by_hour[ts.hour].append(v)
    baseline = {h: statistics.median(vs) for h, vs in by_hour.items()}

    breach = [v < baseline[ts.hour] * 0.5 for ts, v in series]

    print("  Require the condition to hold for N consecutive periods.\n")
    print(f"  {'duration':>12} {'alerts':>8} {'true':>7} {'FALSE':>7} "
          f"{'missed':>8}")
    print("  " + "-" * 50)

    out = {}
    for n in (1, 2, 3):
        fired = set()
        for i in range(len(series) - n + 1):
            if all(breach[i + j] for j in range(n)):
                fired.add(i)
        tp = len(fired & incidents)
        fp = len(fired - incidents)
        fn = len(incidents - fired)
        out[n] = {"fired": len(fired), "tp": tp, "fp": fp, "fn": fn}
        label = f"{n} period" + ("s" if n > 1 else "")
        print(f"  {label:>12} {len(fired):>8} {tp:>7} {fp:>7} {fn:>8}")

    print("\n  **A duration window trades detection latency for silence.**")
    print("  Requiring two consecutive breaches removes single-sample")
    print("  spikes - a scrape that failed, one slow minute - at the cost")
    print("  of noticing a real outage one period later.")

    print("\n  Note the injected incidents here are SINGLE hours, so a long")
    print("  duration window starts missing them entirely. That is the")
    print("  honest trade, not a flaw: a window longer than your incidents")
    print("  cannot see them.")

    print("\n  In practice this is the first knob to reach for, because it")
    print("  costs nothing and removes most flapping.")
    return out


# ============================================ 5. metric types
def metric_types() -> None:
    banner("5. Metric types, and which alert belongs on which")

    rows = [
        ("GAUGE", "a value at a point in time", "CPU %, queue depth, lag"),
        ("DELTA", "the change since the last sample", "requests in this minute"),
        ("CUMULATIVE", "a monotonically rising total", "total bytes, total errors"),
        ("DISTRIBUTION", "a histogram of values", "latency - gives percentiles"),
    ]
    print(f"  {'type':<14} {'what it holds':<34} example")
    print("  " + "-" * 74)
    for a, b, c in rows:
        print(f"  {a:<14} {b:<34} {c}")

    print("\n  **Alert on a DISTRIBUTION with a percentile, never on a mean.**")
    print("  A mean latency of 200 ms is compatible with 5% of users seeing")
    print("  4 seconds. p95 and p99 are what the user experiences; the mean")
    print("  is what makes a dashboard look calm.")

    print("\n  **A CUMULATIVE counter only rises**, so a raw threshold on it")
    print("  fires once and never clears. Alert on its RATE.")

    print("\n  For a data pipeline specifically, the metric worth alerting on")
    print("  is usually **freshness** - how long since the last successful")
    print("  load - rather than row counts or job status. It is one number,")
    print("  it has no seasonality, and it catches silent failure: a job")
    print("  that succeeds while processing nothing does not change its")
    print("  status, and does change its lag.")


def main() -> None:
    if not TRIPS.exists():
        raise SystemExit(f"  {TRIPS} not found - run 00_setup/make_data.py first.")

    print("=" * 72)
    print("  ALERTING - why a static threshold pages at 3am".center(72))
    print("=" * 72)

    rng = random.Random(SEED)
    series, incidents = inject_incidents(hourly_series(), rng)

    d = describe(series)
    s = static_threshold(series, incidents)
    b = seasonal_baseline(series, incidents)
    w = duration_window(series, incidents)
    metric_types()

    best_static = max(s, key=lambda k: s[k]["precision"])
    best_seasonal = max(b, key=lambda k: b[k]["precision"])

    banner("Summary - measured")
    print(f"  - the metric's busiest hour is "
          f"{d['peak'] / max(d['trough'], 1):.0f}x its quietest")
    print(f"  - {N_INCIDENTS} real incidents were injected")
    print(f"  - best STATIC threshold : {s[best_static]['fired']} alerts, "
          f"{s[best_static]['fp']} false, "
          f"{s[best_static]['precision']:.0%} precision")
    print(f"  - best SEASONAL baseline: {b[best_seasonal]['fired']} alerts, "
          f"{b[best_seasonal]['fp']} false, "
          f"{b[best_seasonal]['precision']:.0%} precision")
    print("\n  Alerting on a seasonal metric with a fixed number is not a")
    print("  tuning problem - it is the wrong condition. Normalise the")
    print("  metric, or compare each period against its own history.")


if __name__ == "__main__":
    main()
