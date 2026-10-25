# BigQuery — what each illustration shows

The README explains the *service*. This file explains the *artifacts*: what they set up, what they
measure, and — for the one simulation in this repository — exactly what it does and does not prove.

---

## `partition_pruning.py` — the three cost levers 🔬

**This is a labelled simulation, and the label matters.** BigQuery has no local emulator. The
script builds **Parquet** files and measures bytes read from them. Parquet is columnar with
per-row-group min/max statistics — **the same mechanism** Capacitor uses. So:

- the **ratios demonstrate the mechanism** ✅
- the **absolute numbers are not BigQuery's** ❌

Nothing in this repository presents a Parquet or DuckDB result as a BigQuery result.

**Setup:** the 50,000-trip dataset written three ways — unpartitioned, partitioned by date, and
partitioned + sorted (clustered) on `start_station`.

| § | it does | measured | the exam idea |
|---|---|---|---|
| 1 | Reads 2 of 10 columns vs all 10 | **11.8×** less | `SELECT *` is a **cost bug**, not a style preference |
| 2 | Filters to 1 day of 14, partitioned | **13.3×** less | partitioning **reduces cost** by skipping segments |
| 3 | Filters by station, clustered vs not | **6.2×** vs **1.0×** | clustering **improves speed** via block min/max |

**The 1.0× is the most useful number here.** It is the *unclustered* run of the identical query:
block pruning cannot rule anything out when the values are scattered across every block. That is
precisely what a clustering column missing from your predicate is worth — nothing.

### The failure this is really about

Pruning **fails silently**. Wrap a partition column in a function —

```sql
WHERE DATE(TIMESTAMP_TRUNC(trip_date, DAY)) = '2026-06-09'   -- scans EVERYTHING
```

— and BigQuery returns the **correct answer** while scanning the whole table. No error, no warning,
just the full-table bill. `require_partition_filter = true` converts that mistake into an error,
which is why it belongs on any large table.

## `bigquery_patterns.sql` — real SQL, never submitted 📝

Correct GoogleSQL that would run in the free sandbox. It is **not executed** by this repo, and is
not presented as though it were.

| it covers | the point |
|---|---|
| `CREATE TABLE … PARTITION BY … CLUSTER BY` | partitioning and clustering are declared at DDL |
| pruning that works vs pruning that silently doesn't | the function-wrapped predicate above |
| `--dry_run`, `--maximum_bytes_billed` | the free estimate, and the only hard per-query stop |
| logical / authorized / materialized views | three different jobs — see README §6 |
| `UNNEST` over nested and repeated fields | BigQuery's answer to a join you'd otherwise pay for |
| `INFORMATION_SCHEMA.JOBS` | find the most expensive queries and who ran them |
| time travel (`FOR SYSTEM_TIME AS OF`) | 2–7 days of recovery without a backup |
| `MERGE` | the idempotent upsert that makes at-least-once delivery safe |

---

## Why there is no emulator section

Pub/Sub, Bigtable and Firestore all ship official emulators, and this repo runs them. **BigQuery
does not have one.** The three honest options are: real SQL you can paste into the free sandbox,
a clearly-labelled local simulation of the *mechanism*, or nothing. This section does the first
two and says so in both files.

Everything else in README §§5–9 — slots, Editions, BI Engine, Omni, BigLake, Storage Write API,
DTS, Datastream, Analytics Hub, `INFORMATION_SCHEMA` — is **documented, not demonstrated**. There
is no local proxy for a billing model or a managed cache.
