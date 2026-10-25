# Sensitive Data Protection — what the illustration shows

The README explains the *service*. This file explains the *script*: what it measures, and the one
result that contradicts how de-identification is usually described.

---

## `deidentification.py`

**Setup:** pure Python over the same 50,000 trips. The transforms are ordinary algorithms — HMAC,
bucketing, masking, date shifting — so they run for real. **No DLP API is called and none is
simulated.**

| § | it does | measured |
|---|---|---|
| 1 | pseudonymises 50,000 identifiers with a keyed hash | **100.0% uniqueness preserved** |
| 2 | buckets a continuous field at increasing widths | 54.6% → 1.6% → **0.0%** at risk |
| 3 | masks and redacts | value hidden, row still distinguishable |
| 4 | shifts dates by a consistent per-user offset | intervals preserved, calendar dates not |

## §1 — the result that matters

```
50,000 distinct ids in  ->  50,000 distinct tokens out  ->  100.0% uniqueness
```

**It has to be 100%.** A hash is a function: distinct inputs give distinct outputs. So every row
remains **individually distinguishable, linkable across datasets, and trackable over time**.

> **"We hashed the IDs, so it's anonymous" is false.** It is *pseudonymised* — a different thing,
> still personal data under most regimes, and re-identifiable by anyone with the key, the lookup
> table, or enough surrounding context.

**Reversible and joinable are different properties**, and conflating them is the common error. A
hash is not reversible without a lookup — but it *is* joinable, and joinability is exactly what
lets someone link records back to a person.

## §2 — the only transform that moves the number

| duration held as | groups | groups of 1 | at risk |
|---|---|---|---|
| exact value | 27,591 | 15,076 | **54.6%** |
| bucketed, width 5 | 191 | 3 | 1.6% |
| bucketed, width 30 | 45 | **0** | **0.0%** |

**Generalisation works because it genuinely discards information.** People collapse into groups and
become indistinguishable. That is also its price — and it is the same trade as the aggregation
threshold in [`08_sharing_and_viz`](../../08_sharing_and_viz/01_sharing/): **you buy privacy with
resolution**, and the analysis that needed the resolution stops working.

> **Masking and hashing protect a value. Only generalisation protects a person.**

## The honesty note on FPE

The format-preserving row in the README's transform table is demonstrated with a **toy**
construction, not real FF1/FF3. It is flagged as such, and the direction of the error matters:

> The toy **understates** the risk relative to a proper implementation — which is the wrong
> direction to be wrong in. So treat real FPE as a cryptographic primitive with real key
> management, not as the thing this script does.

## What a local script cannot show

Not demonstrated, and not simulated: **inspection** — infoType detection, likelihood scoring,
custom infoTypes, discovery scans over GCS/BigQuery/Cloud SQL, de-identification templates,
sampling, or Pub/Sub-triggered quarantine.

**Finding the PII is the part that needs the service.** Transforming it, once found, is
arithmetic — and that is the half this script runs.
