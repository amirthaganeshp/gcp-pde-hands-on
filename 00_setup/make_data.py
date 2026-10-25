"""Generate the synthetic bike-share trip stream every section uses.

One dataset, chosen so that every PDE topic has something real to bite on:

  - a genuine EVENT TIME vs PROCESSING TIME skew, so windowing and
    watermarks are observable rather than asserted
  - deliberately LATE events, so triggers and allowed-lateness do
    something visible
  - a natural partition key (date) and cluster key (station) for the
    BigQuery section
  - a small stations dimension to join against, for Spark shuffle

Nothing is downloaded and nothing is real. Seeded, so every number in
every README reproduces.

Run:
    python 00_setup/make_data.py            # default 50k trips
    python 00_setup/make_data.py --trips 500000 --out data/
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 42
REPO = Path(__file__).resolve().parent.parent

# Neutral, positive subject matter: city bike share.
STATIONS = [
    ("ST01", "Riverside Park", 41.881, -87.623, "north"),
    ("ST02", "Union Square", 41.876, -87.640, "central"),
    ("ST03", "Harbour Point", 41.892, -87.610, "north"),
    ("ST04", "Botanic Gardens", 41.862, -87.652, "south"),
    ("ST05", "Museum Mile", 41.870, -87.634, "central"),
    ("ST06", "Old Docks", 41.858, -87.618, "south"),
    ("ST07", "Campus West", 41.901, -87.661, "west"),
    ("ST08", "Market Street", 41.884, -87.648, "central"),
]

BIKE_TYPES = ["classic", "electric", "cargo"]
BIKE_WEIGHTS = [0.68, 0.28, 0.04]


def haversine_km(a_lat, a_lon, b_lat, b_lon) -> float:
    r = 6371.0
    dlat, dlon = math.radians(b_lat - a_lat), math.radians(b_lon - a_lon)
    h = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat))
         * math.sin(dlon / 2) ** 2)
    return round(2 * r * math.asin(math.sqrt(h)), 3)


def demand_multiplier(ts: datetime) -> float:
    """Commuter peaks on weekdays, a leisure bump at weekends."""
    hour = ts.hour
    if ts.weekday() < 5:
        if 7 <= hour <= 9:
            return 3.2
        if 16 <= hour <= 18:
            return 3.6
        if 0 <= hour <= 5:
            return 0.15
        return 1.0
    if 10 <= hour <= 16:
        return 2.1
    if 0 <= hour <= 6:
        return 0.2
    return 1.0


def generate(n_trips: int, days: int, late_fraction: float, rng: random.Random):
    """Yield trip dicts with BOTH event time and processing time.

    The gap between them is the whole point. Most events arrive within
    seconds; a deliberate minority arrive minutes late, which is what
    makes watermarks and allowed-lateness demonstrable in section 02.
    """
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    n_late = 0

    # Accept/reject sampling against the demand curve so the stream has a
    # realistic shape rather than a uniform one.
    made = 0
    while made < n_trips:
        offset = rng.random() * days * 86400
        event_time = start + timedelta(seconds=offset)
        if rng.random() > demand_multiplier(event_time) / 3.6:
            continue

        a = rng.randrange(len(STATIONS))
        b = rng.randrange(len(STATIONS))
        while b == a:
            b = rng.randrange(len(STATIONS))
        s, e = STATIONS[a], STATIONS[b]

        km = haversine_km(s[2], s[3], e[2], e[3])
        bike = rng.choices(BIKE_TYPES, BIKE_WEIGHTS)[0]
        speed = {"classic": 13.0, "electric": 18.0, "cargo": 10.5}[bike]
        minutes = max(1.0, (km / speed) * 60 * rng.uniform(0.75, 1.9))

        # Processing-time lag. Most rows land promptly; a tail does not.
        if rng.random() < late_fraction:
            lag = rng.uniform(120, 900)        # 2-15 minutes late
            n_late += 1
        else:
            lag = rng.uniform(0.5, 20)

        made += 1
        yield {
            "trip_id": f"T{made:08d}",
            "event_time": event_time.isoformat(),
            "processing_time": (event_time + timedelta(seconds=lag)).isoformat(),
            "lag_seconds": round(lag, 1),
            "start_station": s[0],
            "end_station": e[0],
            "bike_type": bike,
            "duration_min": round(minutes, 2),
            "distance_km": km,
            "member": rng.random() < 0.72,
        }

    generate.late_count = n_late


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--trips", type=int, default=50_000)
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--late-fraction", type=float, default=0.08,
                   help="share of events arriving minutes late, not seconds")
    p.add_argument("--out", default=str(REPO / "data"))
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    print(f"  Generating {args.trips:,} trips over {args.days} days, "
          f"seed {SEED}")

    rows = list(generate(args.trips, args.days, args.late_fraction, rng))
    late = getattr(generate, "late_count", 0)

    trips_csv = out / "trips.csv"
    with trips_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # Newline-delimited JSON too: it is what BigQuery and Pub/Sub want.
    # Provided for that kind of loading only - no script in this repo reads
    # it (01_ingestion publishes small inline messages; the capstone reads
    # trips.csv).
    trips_jsonl = out / "trips.jsonl"
    with trips_jsonl.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    stations_csv = out / "stations.csv"
    with stations_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["station_id", "name", "lat", "lon", "district"])
        w.writerows(STATIONS)

    lags = sorted(r["lag_seconds"] for r in rows)
    print(f"\n  {'file':<28} {'rows':>9}  {'size':>9}")
    print("  " + "-" * 50)
    for f in (trips_csv, trips_jsonl, stations_csv):
        n = len(rows) if f.name.startswith("trips") else len(STATIONS)
        print(f"  {f.name:<28} {n:>9,}  {f.stat().st_size / 1e6:>7.2f} MB")

    print(f"\n  Event-time / processing-time lag (the point of this dataset):")
    print(f"    median {lags[len(lags)//2]:>7.1f} s")
    print(f"    p95    {lags[int(len(lags)*0.95)]:>7.1f} s")
    print(f"    max    {lags[-1]:>7.1f} s")
    print(f"    {late:,} of {len(rows):,} events ({late/len(rows):.1%}) arrive "
          f"MINUTES late, not seconds.")
    print("\n  That tail is what makes watermarks and allowed-lateness")
    print("  observable in 02_beam_dataflow rather than merely described.")


if __name__ == "__main__":
    main()
