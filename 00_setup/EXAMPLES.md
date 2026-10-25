# Setup — what running it produces, and how to check it

The README explains **why the dataset is shaped the way it is**. This file covers the other half:
what the script actually emits, and how to verify the reproducibility claim the rest of the
repository rests on.

---

## `make_data.py`

```bash
python 00_setup/make_data.py
```

**Output, as printed by the run:**

```
Generating 50,000 trips over 14 days, seed 42

file                              rows       size
--------------------------------------------------
trips.csv                       50,000     5.83 MB
trips.jsonl                     50,000    14.18 MB
stations.csv                         8     0.00 MB

Event-time / processing-time lag (the point of this dataset):
  median    11.2 s
  p95      423.5 s
  max      899.9 s
  4,011 of 50,000 events (8.0%) arrive MINUTES late, not seconds.
```

| file | bytes | used by |
|---|---|---|
| `data/trips.csv` | 5,832,907 | **every script that reads data** — Beam, Spark, BigQuery, storage, CDC, sharing, governance, monitoring, and the capstone (which publishes these rows to the Pub/Sub emulator) |
| `data/trips.jsonl` | 14,182,791 | **no script reads it** — provided for BigQuery / Pub/Sub-style loading only. `01_ingestion` publishes small inline messages |
| `data/stations.csv` | 358 | the small dimension — side inputs, broadcast joins, CoGroupByKey |

## The reproducibility claim, verified

Every number quoted across ~49 READMEs assumes this dataset is deterministic. That is checkable,
so it was checked: **generate, hash, regenerate, hash again.**

```
BEFORE                                                             AFTER
e967a4ee6fb59edd…  data/trips.csv        ==        e967a4ee6fb59edd…
b2e833a43e0a1227…  data/stations.csv     ==        b2e833a43e0a1227…
d0ecc20ee19a633c…  data/trips.jsonl      ==        d0ecc20ee19a633c…

RESULT: IDENTICAL — the seed reproduces byte for byte
```

> **So if a figure in a README disagrees with a fresh run, the README is wrong.** That is the
> property that makes every measurement in this repository falsifiable rather than merely asserted,
> and it is why regenerating the data is safe at any point.

## The late tail, which is the whole design

**4,011 of 50,000 events (8.0%) arrive minutes rather than seconds late** — median lag 11.2 s, p95
**423.5 s**, max 899.9 s.

This is not incidental noise. Generated without it:

- `02_beam_dataflow` measures nothing — every window closes cleanly and `allowed_lateness` looks
  like a setting with no effect
- the **23.9% / 7.6% / 1.3%** late-rate-by-window-size result does not exist
- the **273 trips (0.5%)** that land in a different *hour* depending on which clock you use do not
  exist
- the capstone's late-data failure has nothing to demonstrate

**The dataset was designed backwards from what each section needed to prove**, and this tail is the
single most load-bearing property.

## Regenerating and scaling

```bash
python 00_setup/make_data.py                        # 50,000 trips (default)
python 00_setup/make_data.py --trips 500000 --out data/
```

**Ratios hold at larger sizes; absolute timings do not.** Every duration quoted in the READMEs was
measured at 50,000 trips on one laptop — scale the data and the pruning ratios, skew factors and
late-rates stay put while the milliseconds move.

## What this is not

**Nothing is downloaded and nothing is real.** These trips demonstrate *mechanisms* — pruning
ratios, skew, lateness, re-identification risk. They are not a model of bike-share behaviour and no
conclusion about cycling should be drawn from them.

The subject matter is deliberately neutral: no employer data, no customer data, no real
identifiers, nothing about illness or disaster — which matters when the same rows are used to
demonstrate PII handling in
[`10_governance_security`](../10_governance_security/01_sensitive_data/).
