# Datastream and CDC

> **Domain 2 — Ingesting and Processing (25%)** · Success Guide pp. 27–30 · Ultimate §2.3
> **Runtime:** <1 s · **Needs:** nothing — pure Python

```bash
python 07_migration_cdc/01_datastream/cdc_patterns.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

---

## 1. What it is

**Datastream is serverless change data capture.** It reads a source database's **transaction /
binary log** — not the tables — and streams every insert, update and delete onward with minimal
load on the source.

| | |
|---|---|
| **Sources** | Oracle, MySQL, PostgreSQL, AlloyDB, SQL Server |
| **Sinks** | **BigQuery** (direct, via BigQuery CDC + Storage Write API) or **Cloud Storage** (Avro/JSON) |
| **Shape** | automatic historical **backfill**, then continuous replication |

Reading the log rather than polling the tables is what makes it low-impact: no `SELECT * WHERE
updated_at > …` scanning the production database every minute.

## 2. Components

| component | what it is |
|---|---|
| **Connection profile** | Source and destination definitions, reused across streams. |
| **Stream** | One source → one destination, with an object/table include list. |
| **Backfill** | The historical snapshot, run once per object. |
| **CDC events** | `INSERT` / `UPDATE` / `DELETE` records carrying metadata. |
| **LSN / SCN / binlog position** | The source's **monotonic sequence number**. |
| **Tombstone** | A delete event. |

## 3. The semantics — what the illustration measures

A CDC stream is **not rows, it is a log of changes**. Turning it back into current state is where
the errors live.

| rule | why |
|---|---|
| **Order by the source's LSN, never by arrival time** | events can arrive out of order; the log's sequence number is the only truth |
| **Take the last change per key** | an updated-three-times row is one row, not three |
| **Honour tombstones** | a merge that ignores deletes **resurrects deleted rows** |
| **Deduplicate** | delivery is at-least-once, so the same event can appear twice |

**Measured** (`cdc_patterns.py`): applying the change log naively produced **464 rows against a
ground truth of 461**.

> **Three rows wrong is the point.** It is close enough to pass a row-count sanity check, close
> enough to look right on a dashboard, and completely wrong for anyone who was deleted. Silent
> failures like this are why `99_reference/FINDINGS.md` §2 exists.

The correct shape is an idempotent `MERGE` on the **business key**, ordered by LSN, with deletes
applied:

```sql
MERGE `analytics.trips` T
USING (
  SELECT * EXCEPT(rn) FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY trip_id ORDER BY source_lsn DESC   -- LSN, not arrival time
    ) AS rn
    FROM `staging.trips_cdc`
  ) WHERE rn = 1                                       -- last change per key
) S
ON T.trip_id = S.trip_id
WHEN MATCHED AND S.op = 'DELETE' THEN DELETE           -- honour the tombstone
WHEN MATCHED THEN UPDATE SET ...
WHEN NOT MATCHED AND S.op != 'DELETE' THEN INSERT ...
```

## 4. Nuances — the part worth reading

**Datastream replicates; it does not transform.** No schema conversion, no business logic. If the
target shape differs, something downstream does that work — Dataform, a Dataflow job, or a
scheduled `MERGE`.

**BigQuery CDC needs a primary key declared** on the destination table, or the merge has nothing to
match on.

**Backfill and streaming are different load profiles.** The initial backfill of a large table is a
heavy read; the ongoing stream is light. Sizing judged on the steady state will be wrong on day
one.

**Schema drift is the standing operational risk.** A column added at the source has to be handled
downstream — this is the most common reason a long-running stream starts dropping fields.

**At-least-once means duplicates are normal**, exactly as in [Pub/Sub](../../01_ingestion/01_pubsub/).
The `MERGE` above is idempotent, which is what makes that acceptable rather than corrupting.

## 5. Datastream vs the alternatives

| | **Datastream** | **DMS** | **DTS** |
|---|---|---|---|
| goal | **replicate, keep both** | **migrate, then stop using the source** | **scheduled loads** |
| ends? | no — ongoing | yes, at promotion | recurring |
| converts schema? | no | **yes** | no |
| target | BigQuery, GCS | Cloud SQL, AlloyDB, Spanner | BigQuery |

**Use Datastream when** the requirement is *near-real-time analytics on operational data* without
self-managed staging tables or hand-written merge logic.

## 6. What was actually run

| | |
|---|---|
| `cdc_patterns.py` | ✅ **fully executed** — pure Python, no service |
| Cloud resources | **none** |

📝 **Documented, not demonstrated:** the Datastream service itself, connection profiles, backfill
behaviour, BigQuery CDC, schema-drift handling. The script models **the semantics of a change log**,
which is the part that actually goes wrong, and does not pretend to be the product.
