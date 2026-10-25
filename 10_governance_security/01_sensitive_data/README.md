# Sensitive Data Protection (formerly Cloud DLP)

> **Domain 1 — Designing Data Processing Systems (22%)** · Success Guide pp. 14–17 · Ultimate §1.3
> **Runtime:** ~1 s · **Needs:** nothing

```bash
python 10_governance_security/01_sensitive_data/deidentification.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

> **Naming.** Cloud DLP is now **Sensitive Data Protection**. The API kept its old name — it is
> still the *Cloud Data Loss Prevention API*, still `dlp.googleapis.com`. See
> [`99_reference/SERVICE_NAMES.md`](../../99_reference/SERVICE_NAMES.md).

---

## 1. What it is

A service that **discovers, classifies and transforms** sensitive data. Two halves, and they are
often confused:

- **Inspection** — find it. `infoTypes` are detectors (`CREDIT_CARD_NUMBER`,
  `US_SOCIAL_SECURITY_NUMBER`, emails, phone numbers), each match carrying a *likelihood* from
  `VERY_UNLIKELY` to `VERY_LIKELY`. Custom infoTypes use regex, dictionaries or surrogates.
- **De-identification** — change it. The transforms below.

## 2. Components

| component | what it is |
|---|---|
| **infoType** | A detector. Built-in, or custom (regex / dictionary / surrogate). |
| **Likelihood** | Confidence of a match. Threshold it — `POSSIBLE` is noisy. |
| **Inspection job** | Scans a bucket, table or stream. |
| **De-identify template** | A reusable set of transforms. |
| **Crypto key** | Wrapped by **Cloud KMS** — never a literal in the config. |

## 3. The transforms

| transform | reversible | joinable | same format | note |
|---|---|---|---|---|
| masking | no | no | yes | display only |
| redaction | no | no | n/a | the column is gone |
| **pseudonymisation** (HMAC) | with a lookup | **yes** | no | joins survive |
| **format-preserving** (FF1/FF3) | with the key | **yes** | **yes** | fits the column |
| **generalisation** (bucketing) | no | partly | no | **the only real risk cut** |
| date shifting | with the key | yes | yes | intervals survive |

## 4. Running it in production

### In-flight de-identification — the reference architecture

```
raw PII --> Pub/Sub --> Dataflow --> BigQuery
                          |  ^         (clean, analytical)
                          v  |
               Sensitive Data Protection API
               (via a de-identification TEMPLATE)
```

Dataflow calls the API per micro-batch and writes **only sanitised records** onward. The raw PII
never reaches the warehouse, which is the point — de-identifying after landing means the
unprotected copy already exists.

### Scanning what you already have

Scheduled **discovery / inspection jobs** run directly against Cloud Storage, BigQuery and Cloud
SQL, producing profiles that pinpoint where unencrypted PII has leaked into production. They can
publish to **Pub/Sub** to trigger a Cloud Function that quarantines or remediates the object
automatically.

### Cost — the part the exam tests

| lever | why |
|---|---|
| **Inspection / de-identification templates** | configure once, reference by name — smaller API payloads and lower latency than inlining the config per call |
| **Sampling** | scan a **percentage** of files or bytes to establish *whether* PII is present, rather than 100% of cold storage |

> **Calling the API on every record in a high-throughput pipeline is expensive.** Templates plus
> sampling is the standard answer to "how do we do this affordably at scale".

### The two scenarios worth memorising

| requirement | answer |
|---|---|
| "share real employee records with a legacy app that demands an **8-digit ID**" | **FPE** — hides the value, keeps the format |
| "statistical analysis: don't identify users, but still **join transactions** and **measure the time between them**" | **cryptographic hashing** (deterministic, so joins survive) **+ date shifting** (consistent per-user offset, so intervals survive) |

## 5. Nuances — the part worth reading

**Hashing does not reduce re-identification risk. Measured:**

| representation | distinct values | uniqueness |
|---|---|---|
| original | 50,000 | 100.0% |
| **pseudonymised (HMAC)** | **50,000** | **100.0%** |

It *has* to — a hash is a function, so distinct inputs give distinct outputs. **Every row remains
individually distinguishable, linkable across datasets, and trackable over time.**

> "We hashed the IDs, so it's anonymous" is **false**. It is *pseudonymised* — a different thing,
> still personal data under most regimes, and re-identifiable by anyone with the key, the lookup
> table, or enough context.

**Reversible and joinable are different properties, and conflating them is the common error.** A
hash is not reversible without a lookup, but it *is* joinable — and joinability is what lets
someone link records back to a person.

**Generalisation is the only transform that moves the number:**

| duration held as | groups | groups of 1 | at risk |
|---|---|---|---|
| exact value | 27,591 | 15,076 | **54.6%** |
| bucketed, width 5 | 191 | 3 | 1.6% |
| bucketed, width 30 | 45 | **0** | **0.0%** |

It works because it genuinely **discards information** — people collapse into groups and become
indistinguishable. That is also its price, and it is the same trade as the aggregation threshold in
[`08_sharing_and_viz`](../../08_sharing_and_viz/): you buy privacy with resolution, and the
analysis that needed the resolution stops working.

> **Masking and hashing protect a value. Only generalisation protects a person.**

**Date shifting needs a per-entity offset.** Measured: intervals survive exactly. Get the scope
wrong and it fails in both directions —

- **one offset for everyone** → any known event reveals the offset and undoes the whole dataset
- **a new offset per row** → intervals are destroyed, and the data is useless for the analysis it
  was kept for

**Keys belong in Cloud KMS**, and the de-identify config references a wrapped key rather than
containing one. A crypto transform with a key in the job definition is not protecting anything from
whoever can read the job definition.

## 6. When to use which

| situation | transform |
|---|---|
| show the last 4 digits in a UI | **masking** |
| the column is not needed at all | **redaction** |
| must still join across systems | **pseudonymisation** |
| must fit a column expecting the original shape | **format-preserving** |
| publishing, or sharing externally | **generalisation** |
| longitudinal analysis without real dates | **date shifting** |

**For anything leaving your control, generalisation or nothing.** The other transforms are for data
that stays inside a trust boundary.

## 7. What was actually run

| | |
|---|---|
| `deidentification.py` | ✅ **fully executed**, exit 0 |
| Sensitive Data Protection service | 📝 **write-only** — no local equivalent |

The transforms are ordinary algorithms, so they run. **Inspection — infoType detection, likelihood
scoring, job triggers — does not**, and is the half you would actually buy the service for.

**One number in the output is an artifact and says so in the file.** The format-preserving row
shows collisions because the toy implementation permutes each character position independently. A
real FF1/FF3 is a **bijection** and would preserve uniqueness at 100%, exactly like the HMAC row.
The toy *understates* the risk, which is the wrong direction to be wrong in — so treat real FPE as
having the same re-identification properties as pseudonymisation, plus format preservation.

The key in this file is a literal marked as a demo. That is precisely what section 4 says not to do
in production.
