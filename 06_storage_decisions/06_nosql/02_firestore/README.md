# Firestore — documents, indexes and limits

> **Domain 3 (20%)** · Success Guide pp. 30–31 · Ultimate §3.3
> **Runtime:** ~5 s · **Needs:** `google-cloud-firestore`, the Firestore emulator, Java

```bash
python 06_storage_decisions/06_nosql/02_firestore/firestore_queries.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

---

## 1. What it is

A document database that **indexes every field automatically** and offers a real query language —
the opposite of Bigtable, which has one sorted index and no queries at all.

The trade: real queries, but constrained ones, and **billing per document read**.

## 2. Components

| component | what it is |
|---|---|
| **Collection** | A namespace. No schema; documents need not match. |
| **Document** | A JSON-like object, typed fields, **max 1 MiB**. |
| **Subcollection** | A collection under a document. **Not loaded with the parent.** |
| **Single-field index** | Created automatically for every field. |
| **Composite index** | Required for multi-field queries. **You must declare it.** |
| **Listener** | A realtime subscription — the thing apps use it for. |
| **Collection group query** | Queries **every** subcollection sharing a name, across all parents. Needs its own index. |
| **Security rules** | Declarative per-document access, evaluated **server-side**, on the client's identity. |

## 3. Fundamental operations

| query | docs | result |
|---|---|---|
| `station == 'ST01'` | 43 | served by an automatic index |
| `station == 'ST01' AND duration > 15` | 9 | **needs a composite index** |
| `duration > 15 ORDER BY station` | 10 | **breaks the ordering rule** |

## 4. Nuances — the part worth reading

**All three queries above succeeded against the emulator. At least one would fail in production —
and that gap is the finding.**

The emulator **creates composite indexes on demand**; production does not. There, query 2 returns
`FAILED_PRECONDITION` with a link to go and create the index. Query 3 breaks a rule the emulator
did not enforce at all: **if you range-filter on a field, your first `order_by` must be that
field**, because Firestore cannot sort by one field while scanning an index ordered by another.

> So "it worked locally" carries less weight here than almost anywhere else in this repository.
> **Keep `firestore.indexes.json` in source control and deploy it**, rather than discovering
> required indexes from production errors one at a time.

**The per-document write limit is the design constraint: roughly one sustained write per second,
per document.** A single counter document updated on every event caps there no matter what else
you do — the Firestore version of a hot key. The fix is a **distributed counter**: shard across N
documents and sum on read.

**Billing per document read shapes the schema.** A query returning 10,000 documents costs 10,000
reads even if you wanted one field from each. Denormalising a summary into the parent to avoid
reading children is not a hack — it is the cost model working as designed.

**Subcollections are not loaded with their parent**, which is what makes deep nesting cheap to
read.

**Other limits worth knowing:** 1 MiB per document, 500 documents per batch or transaction, no
joins, and aggregation limited to count/sum/avg — there is no `GROUP BY`.

**Native mode vs Datastore mode: choose Native for anything new.** Datastore mode exists for App
Engine compatibility and loses realtime listeners and offline sync.

**Security rules are the access model, and they are not IAM.** Mobile and web clients talk to
Firestore *directly*, with no server in between — so per-document authorisation is expressed as
rules evaluated on the client's identity, server-side. IAM governs the project; rules govern the
documents. A scenario about "users may read only their own records from a mobile app" is rules,
not IAM.

**Collection group queries are how you escape the hierarchy.** Nesting `reviews` under each
`product` makes per-product reads cheap but "all recent reviews" impossible — until a collection
group query spans every `reviews` subcollection at once. It needs its own composite index, which
is one more thing the emulator will hand you for free and production will not.

## 5. Firestore or Bigtable?

| | **Firestore** | **Bigtable** |
|---|---|---|
| index | every field, automatic | **the row key, only** |
| queries | filters, ordering, limits | prefix and range scans |
| latency | tens of ms | single-digit ms |
| billed on | document reads/writes | nodes and storage |
| realtime sync | **yes** — listeners, offline | no |
| best at | app state, user data | time series, telemetry |

**Firestore is an application database; Bigtable is an analytical-scale key-value store.** The
giveaway is whether an **app** reads it (mobile, web, offline, realtime → Firestore) or a
**pipeline** does (ingest rate, time series, scans → Bigtable).

**Neither is an analytics store.** "Report across all of it" is BigQuery in both cases — and
Firestore has a managed export to BigQuery for exactly that.

## 6. What was actually run

| | |
|---|---|
| `firestore_queries.py` | ✅ **fully executed**, exit 0 |
| Emulator | Firestore emulator from the gcloud SDK, started and stopped by the script |
| Client | `google-cloud-firestore` **2.32.0** |
| Cloud resources | **none** |

The emulator's **permissiveness is documented as a finding rather than worked around**: it accepted
queries production would reject, and knowing that is more useful than a green tick.
