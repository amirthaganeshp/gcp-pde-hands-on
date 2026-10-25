# Firestore — what the illustration shows

The README explains the *service*. This file explains the *script* — and here the interesting
result is **not** that the queries worked. It is that they worked *locally* and one of them would
not work in production.

---

## `firestore_queries.py`

**Setup:** the **official Firestore emulator**, started and stopped by the script. Documents
written into a collection, then queried three ways.

| # | query | docs | what happened |
|---|---|---|---|
| 1 | `station == 'ST01'` | 43 | served by an **automatic single-field index** |
| 2 | `station == 'ST01' AND duration > 15` | 9 | succeeded — **production needs a composite index** |
| 3 | `duration > 15 ORDER BY station` | 10 | succeeded — **production rejects this outright** |

## All three passed. That is the finding.

**The emulator creates composite indexes on demand. Production does not.**

- **Query 2** in production returns `FAILED_PRECONDITION`, with a link to go and create the index.
- **Query 3** breaks a rule the emulator did not enforce at all: **if you range-filter on a field,
  your first `order_by` must be that field.** Firestore cannot sort by one field while scanning an
  index ordered by another.

> So **"it worked locally" carries less weight here than almost anywhere else in this repository.**
> A query suite that passes cleanly on the emulator can fail on deploy, one index at a time.

**The fix is to treat indexes as code:** keep `firestore.indexes.json` in source control and deploy
it, rather than discovering required indexes from production errors.

## Why this was kept rather than rewritten

An earlier draft of the narration claimed query 3 **failed**. It did not — it succeeded, and the
script's own output said so. Rewriting the query until it failed would have produced a tidier demo
and destroyed the actual lesson, which is about **emulator leniency**, not about that query.

Recorded in [`99_reference/FINDINGS.md`](../../../99_reference/FINDINGS.md) §7 as an honest
negative and §8 as a narration-vs-output correction.

## The constraints the script does not exercise

Worth knowing, and not demonstrated here:

| limit | consequence |
|---|---|
| **~1 sustained write/sec per document** | a single counter document caps there — the Firestore hot key. Fix: a **distributed counter** sharded across N documents, summed on read. |
| **billing per document read** | a query returning 10,000 documents costs 10,000 reads even if you wanted one field. Denormalising a summary into the parent is the cost model working as designed. |
| **1 MiB per document, 500 per batch/transaction** | hard ceilings |
| **no joins; only count/sum/avg** | there is no `GROUP BY` |

## What the emulator cannot show

Not demonstrated, and not simulated: index build behaviour, security rules evaluation, realtime
listeners, offline sync, collection group queries at scale, multi-region replication, or the write
throughput limits above.

**The emulator is a correctness aid for basic operations and is actively misleading about
indexes** — which is the single most useful thing to know about it.
