# Datastream / CDC — what the illustration shows

The README explains the *service*. This file explains the *script*: what it builds, what it
measures, and why three wrong rows are worse than three hundred.

---

## `cdc_patterns.py`

**Setup:** pure Python — no service, no emulator. The script **constructs a change log** (inserts,
updates, deletes, with source sequence numbers and deliberate out-of-order arrival) and a **ground
truth** of what the table should contain after applying it. Then it applies the log two ways.

| § | it does | measured |
|---|---|---|
| 1 | builds a change log with a known correct end state | ground truth: **461 rows** |
| 2 | applies it **naively** — last arrival wins, deletes ignored | **464 rows** |
| 3 | decomposes the difference | **6 stale values**, **3 resurrected deletes** |
| 4 | applies it correctly — order by LSN, last per key, honour tombstones | matches truth exactly |

## 464 against 461 — why this is the sharpest result in the repo

```
truth  : 461 rows
naive  : 464 rows        <- 0.65% off
```

**A row-count sanity check passes.** A dashboard looks right. A spot check of ten rows finds
nothing. And inside that 0.65% are **three people who asked to be deleted and are still in the
table**, plus six rows showing values that were superseded.

> This is the cleanest example in the repository of the category in
> [`99_reference/FINDINGS.md`](../../99_reference/FINDINGS.md) §2 — **failures that raise
> nothing**. A big error announces itself; a small one ships.

## The four rules, and what each one fixes

| rule | what breaks without it |
|---|---|
| **Order by the source LSN/SCN, not arrival time** | an update that arrives late overwrites a newer one |
| **Take the last change per key** | a row updated three times becomes three rows |
| **Honour tombstones** | **deletes are resurrected** — the three above |
| **Deduplicate** | at-least-once delivery counts the same change twice |

The correct shape is an idempotent `MERGE` on the **business key**:

```sql
MERGE `analytics.trips` T
USING (
  SELECT * EXCEPT(rn) FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY trip_id ORDER BY source_lsn DESC   -- LSN, not arrival
    ) AS rn
    FROM `staging.trips_cdc`
  ) WHERE rn = 1                                       -- last change per key
) S
ON T.trip_id = S.trip_id
WHEN MATCHED AND S.op = 'DELETE' THEN DELETE           -- the tombstone
WHEN MATCHED THEN UPDATE SET ...
WHEN NOT MATCHED AND S.op != 'DELETE' THEN INSERT ...
```

**That `MERGE` is idempotent**, which is what makes at-least-once delivery acceptable rather than
corrupting — the same discipline as [Pub/Sub](../../01_ingestion/01_pubsub/) redelivery and
[Airflow](../../05_orchestration/01_composer/) retries.

## Why this is modelled rather than run against Datastream

Datastream needs a real source database with logical replication enabled, a connection profile and
a project. **What actually goes wrong in CDC is not the capture — it is the apply**, and the apply
is ordinary SQL logic that can be modelled exactly.

So the script demonstrates **the semantics of a change log** and makes no claim to be the product.

## What is not demonstrated

The Datastream service itself, connection profiles, backfill behaviour and its load profile,
BigQuery CDC with a declared primary key, schema-drift handling, or replication lag. All
documented in the README, none simulated.
