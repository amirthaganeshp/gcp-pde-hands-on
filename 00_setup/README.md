# Setup — the dataset everything else uses

> **Run this once before anything else.**
> **Runtime:** ~3 s · **Needs:** Python only

```bash
python 00_setup/make_data.py                        # 50,000 trips (default)
python 00_setup/make_data.py --trips 500000 --out data/
```

Walk-through of the output, and the reproducibility check: **[EXAMPLES.md](EXAMPLES.md)**.

---

## 1. What it is

One synthetic bike-share dataset, **designed backwards from what each section needs to
demonstrate**. Nothing is downloaded and nothing is real. It is **seeded**, so every number quoted
in every README reproduces exactly.

| file | grain |
|---|---|
| `data/trips.csv` | one row per trip — the main dataset |
| `data/trips.jsonl` | the same trips as newline-delimited JSON — **provided for BigQuery / Pub/Sub-style loading only; no script in this repo reads it** |
| `data/stations.csv` | 8 stations — the small dimension to join against |

## 2. The columns, and which section needs each

| column | exists because |
|---|---|
| `trip_id` | a business key for idempotent `MERGE` — CDC and BigQuery |
| **`event_time`** | when the trip *happened* |
| **`processing_time`** | when the pipeline *saw* it |
| **`lag_seconds`** | the gap between them — what makes watermarks observable |
| `start_station` / `end_station` | a **high-cardinality** key: clustering, shuffle, row keys, hot keys |
| `bike_type` | a low-cardinality split for `Partition` and filters |
| `duration_min` | a numeric measure to aggregate |
| `distance_km` | a second measure, for correlations and quality rules |
| `member` | a boolean, and a k-anonymity dimension |

## 3. The deliberate properties

**These are design decisions, not accidents of generation:**

| property | measured | without it |
|---|---|---|
| **8.0% of events arrive minutes late** (median lag **11.2 s**, p95 **423.5 s**) | 23.9% late in 1-min windows, 1.3% in 1-hour | watermarks, triggers and `allowed_lateness` would be assertions rather than measurements |
| **event time ≠ processing time** | **273 trips (0.5%)** fall in a different *hour* | the two clocks would look interchangeable |
| **date is a natural partition key** | partition pruning **13.3×** | nothing to prune |
| **station is a natural cluster key** | block pruning **6.2× vs 1.0×** | clustering would be unmeasurable |
| **8 stations, unevenly used** | hot-key skew across five services | no hot key to find |
| **a small stations dimension** | side inputs / broadcast joins | the small-table join would have no small table |

> **The late tail is the single most important property.** Generate this data without it and half
> of `02_beam_dataflow` measures nothing — every window would close cleanly, and
> `allowed_lateness` would appear to be a setting with no effect.

## 4. Nuances — the part worth reading

**Synthetic data is a claim, and it should be a modest one.** These trips demonstrate *mechanisms*
— pruning ratios, skew, lateness. They are not a model of real bike-share behaviour and no
conclusion about cycling should be drawn from them.

**Seeded means reproducible, which means falsifiable.** Every figure in this repository can be
re-derived by running the scripts. If a number here disagrees with a number in a README, the README
is wrong.

**The subject matter is deliberately neutral.** No employer data, no customer data, no real
identifiers, and nothing about illness or disaster — see the de-identification section for why that
matters when the examples are about PII.

**Scale it if you want to.** `--trips 500000` works, and the *ratios* hold; the absolute timings in
the READMEs will not, because they were measured at 50,000 on one laptop.

## 5. What was actually run

| | |
|---|---|
| `make_data.py` | ✅ **fully executed** — 50,000 trips, exit 0 |
| External data | **none** — nothing downloaded |
| Cloud resources | **none** |
