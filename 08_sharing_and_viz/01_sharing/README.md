# Sharing data safely — Analytics Hub, authorised views, clean rooms

> **Domain 4 — Preparing and Using Data for Analysis (15%)** · Success Guide pp. 16, 45 ·
> Ultimate §4.3 · **Runtime:** ~1 s · **Needs:** nothing

```bash
python 08_sharing_and_viz/01_sharing/sharing_privacy.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

---

## 1. What it is

Three mechanisms for letting someone else use your data **without copying it**:

- **Authorised views** — share a slice. You write the query; they see those rows.
- **Analytics Hub** — publish a dataset as a **listing**; subscribers get a *linked dataset* that
  queries your data in place, on their bill, revocable at any time.
- **Data clean rooms** — two parties join data, **neither sees the other's rows**, and only
  aggregates come out.

Copying is the thing they all exist to avoid: the moment data leaves as a copy you lose
revocation, freshness, and any record of who holds what.

## 2. Components

| component | what it is |
|---|---|
| **Listing** | A dataset published into an exchange. |
| **Linked dataset** | The subscriber's read-only pointer. Live, not a copy. |
| **Exchange** | Public, private, or internal — who can discover the listing. |
| **Analysis rule** | The constraint a clean room enforces on queries. |
| **Aggregation threshold** | Minimum group size a result may have. |
| **Policy tag** | Column-level access control, via a taxonomy. |
| **Row-level policy** | A filter applied per principal. |

## 3. Analytics Hub — roles and who pays

| role | can |
|---|---|
| `analyticshub.admin` | create/update/delete **exchanges**, manage publishers and subscribers |
| `analyticshub.publisher` | create/update/delete **listings** — decides what gets exposed |
| `analyticshub.listingAdmin` | update/delete existing listings and their IAM — **cannot create new ones** |
| `analyticshub.subscriber` | discover and subscribe, creating the **linked dataset** in their project |
| `analyticshub.viewer` | browse listings — **cannot subscribe or query** |

> **The subscriber pays for compute.** They query the linked dataset using their own project's
> slots or on-demand bytes. The publisher pays only for storage — which is what makes publishing
> to thousands of partners economically sane, and is a favourite exam detail.

**Clean room analysis rules — the three the exam names:**

| rule | enforces |
|---|---|
| **Aggregation threshold** | a result row must represent at least *k* contributing entities |
| **List overlap** | only the **intersection** of both parties' keys is returned — no unmatched rows leak |
| **Differential privacy** | calibrated noise added, with a privacy budget that depletes as queries run |

**Only explicitly added subscribers can query a clean room**, and none of them can read the raw
rows — that is the entire difference from a standard exchange.

## 4. Fundamental operations

The script measures why thresholds exist, rather than asserting it.

## 5. Nuances — the part worth reading

**Aggregation is not anonymisation, and every extra column makes it worse.** Measured on the same
50,000 trips:

| dimensions (cumulative) | groups | smallest | size 1 |
|---|---|---|---|
| station | 8 | 6,127 | 0 |
| + bike_type | 24 | 219 | 0 |
| + member | 48 | 61 | 0 |
| + end_station | 335 | 4 | 0 |
| **+ hour** | 5,961 | **1** | **1,288** |
| + duration_bucket | 14,052 | 1 | **5,056** |

**Singletons appear at five dimensions**, and by six they are **36% of all groups**. A group of one
*is* a row — "a 20–25 minute cargo-bike trip from Old Docks to Campus West at 06:00 by a
non-member" identifies a person as surely as publishing their name.

Nobody adds a *dangerous* column. They add a *useful* one, and the groups get smaller each time.

**The threshold is a dial with a real cost:**

| k | groups kept | trips kept |
|---|---|---|
| 1 | 14,052 | 100% |
| 3 | 6,344 | 79.3% |
| **5** | **3,484** | **59.7%** |
| 10 | 1,002 | 27.8% |
| 50 | **0** | **0%** |

At k=5 you lose 40% of the data; at k=50 there is nothing left. The rare combinations that vanish
first are often the interesting ones — a genuine privacy/utility trade, not a free setting.

**A clean room returns nothing rather than a small number.** An error would itself leak the
existence of a small group.

**Thresholds protect a query, not a questioner.** Measured: two queries that both clear any
sensible threshold —

```
trips from ST01                    6,258
trips from ST01, excluding cargo   6,009
the difference                       249   <- never aggregated, never checked
```

Repeated with narrower filters, differencing converges on a single row. That is why clean rooms
also constrain **join keys** and available columns, and why query logs are visible to the
publisher. The threshold is necessary and nowhere near sufficient.

## 6. When to use it — and when not

| situation | mechanism |
|---|---|
| another team, same org, live data | authorised view / dataset IAM |
| a partner org, ongoing, revocable | **Analytics Hub listing** |
| two parties joining, neither trusts | **data clean room** |
| hide columns, not rows | policy tags |
| hide rows by who is asking | row-level access policies |
| an external system that must own a copy | scheduled export — last resort |

**Analytics Hub is the default exam answer for cross-organisation sharing** — live, revocable, and
the consumer pays their own query costs, which is usually the detail the question points at.

## 7. What was actually run

| | |
|---|---|
| `sharing_privacy.py` | ✅ **fully executed**, exit 0 |
| Analytics Hub, clean rooms, policy tags | 📝 **write-only** — no local equivalent |

The privacy measurements are real arithmetic on the synthetic dataset — group sizes, singleton
counts, threshold survival, and a differencing attack. The **mechanisms** that enforce them in
BigQuery cannot be run locally.

**The first version of this file did not demonstrate its own point.** Grouping by only three
dimensions gave 48 groups with a smallest of 61 — no singletons at all — so the threshold table
showed no effect and the summary printed "0 of size 1, each of those is a person". Adding
dimensions until small groups genuinely appeared turned that failure into the actual lesson: the
progression itself.
