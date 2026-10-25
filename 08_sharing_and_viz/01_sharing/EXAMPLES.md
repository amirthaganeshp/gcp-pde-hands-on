# Sharing safely — what the illustration shows

The README explains the *services*. This file explains the *script*: what it measures, and why an
aggregation threshold is a real control rather than a formality.

---

## `sharing_privacy.py`

**Setup:** pure Python over the same 50,000 trips every other section uses. It groups them by
progressively more dimensions and counts how many groups end up containing **exactly one person's
activity**.

| dimensions (cumulative) | groups | smallest | groups of size 1 |
|---|---|---|---|
| station | 8 | 6,127 | 0 |
| + bike_type | 24 | 219 | 0 |
| + member | 48 | 61 | 0 |
| + end_station | 335 | 4 | **0** |
| **+ hour** | 5,961 | **1** | **1,288** |
| + duration_bucket | 14,052 | 1 | **5,056** |

## The shape of the result is the finding

**Singletons appear at five dimensions, and by six they are 36% of all groups.**

Nothing is wrong at four dimensions — the smallest group still has four people in it. One more
column and 1,288 groups describe exactly one person. **The transition is abrupt**, which is why
"we only publish aggregates" is not a safety argument on its own.

> **A group of one is a person.** An aggregate over a single individual is that individual's data
> wearing a `GROUP BY`.

## Why this is the argument for an aggregation threshold

The control is not "aggregate the data" — it is "**refuse to return a group smaller than k**".
That is what a clean room's aggregation-threshold analysis rule enforces, and what
`k-anonymity` means in practice.

**And it has a price**: at k=5, 59.7% of trips survive the filter. At k=50, **none do**. You buy
privacy with resolution, and past a certain point the analysis the data was shared for stops
working. Same trade as bucketing in
[`10_governance_security`](../../10_governance_security/01_sensitive_data/).

## Thresholds protect a query, not a questioner

The script's second point. Two queries that each satisfy the threshold can be **differenced**:

```
"trips from ST01"                     -> 6,127     (allowed)
"trips from ST01 excluding member=Y"  -> 6,126     (allowed)
difference                            ->     1     (a person)
```

Neither query broke the rule. **A per-query threshold cannot see across queries**, which is why
serious clean-room settings add a **privacy budget** (differential privacy) that depletes as
questions are asked, rather than evaluating each one in isolation.

## The narration bug this script caught

An earlier version asserted "a group of one is a person" while the run reported **0 singletons** —
the dimension list stopped at four, so the effect it was describing had not happened yet. The fix
was to **add dimensions until singletons actually appeared**, not to soften the sentence.

Recorded in [`99_reference/FINDINGS.md`](../../99_reference/FINDINGS.md) §8.

## What is not demonstrated

Analytics Hub exchanges, listings and linked datasets; clean-room analysis rules executing;
authorised views; policy tags; row-level access policies; differential-privacy budgets. All
documented in the README, none simulated — they need a project and a second party.

**What is real** is the re-identification arithmetic, and it does not depend on which product
enforces the threshold.
