# NoSQL — Bigtable and Firestore

> **Domain 3 — Storing the Data (20%)** · Success Guide pp. 30–33 · Ultimate §3.3
> Both sub-services run against **official Google emulators**. ✅

```bash
python 06_storage_decisions/06_nosql/01_bigtable/row_key_design.py
python 06_storage_decisions/06_nosql/02_firestore/firestore_queries.py
```

| | [**Bigtable**](01_bigtable/) | [**Firestore**](02_firestore/) |
|---|---|---|
| model | **wide-column key-value** | **document** |
| index | **the row key, and nothing else** | automatic single-field + composite indexes |
| latency | **sub-millisecond** point reads | low, with realtime listeners |
| scale | petabytes, linear with nodes | horizontal, managed |
| built for | IoT, time-series, financial ticks, very high write throughput | mobile/web backends, user profiles, offline sync |

---

## 1. The shared idea

Neither of these is a smaller SQL database. **Both make you choose your access pattern up front**,
and then serve it extremely well and nothing else.

- **Bigtable** gives you exactly one index — the row key. Every query is a key lookup or a range
  scan over a *lexicographically sorted* key space.
- **Firestore** indexes automatically, but a multi-field query needs a **composite index** that must
  exist before the query will run.

Get the design wrong and the fix is a migration, not a tuning parameter. **A Bigtable row key
cannot be changed once the table holds data.**

## 2. Relational → NoSQL vocabulary

Worth knowing cold, because the exam asks it directly:

| relational | Datastore | Firestore Native |
|---|---|---|
| Table | Kind | **Collection** |
| Row | Entity | **Document** (JSON-like, **max 1 MB**) |
| Column | Property | **Field** (supports nesting, maps, arrays) |
| Primary key | Key | **Document ID / reference** |
| Nested table / join | Ancestor path (parent-child) | **Subcollection** |
| Cross-table query | Ancestor query | **Collection group query** |

**Documents in a collection do not have to share a schema** — which is a feature until it is a
data-quality incident.

## 3. Bigtable's data model

| element | what it is |
|---|---|
| **Row key** | The single index. **Sorted lexicographically.** Immutable after load. |
| **Column family** | A logical group of columns. **Garbage-collection rules live here** — "keep 3 versions", "drop cells older than 30 days". |
| **Column qualifier** | Sparse, dynamic attribute inside a family. |
| **Cell** | A (row, column) intersection, **versioned by descending timestamp**. |
| **Tablet** | A contiguous range of the sorted key space, served by one node. |

**Measured** ([`01_bigtable/`](01_bigtable/)): a timestamp-first key spread a burst of writes
across **1.0 of 8** tablets — every write to one node. Station-first reached **7.9 of 8**.

> That is hot-spotting, quantified. Sequential row keys — timestamps, auto-increment IDs — are the
> classic Bigtable design error. Reverse the domain, hash-prefix, or promote a distinguishing
> field to the front.

## 4. Firestore's query model

**Measured** ([`02_firestore/`](02_firestore/)): all three test queries succeeded against the
emulator — **including one production would reject for a missing composite index.**

> **That result is the finding.** The emulator creates indexes on demand; production does not.
> A query suite that passes locally can fail on deploy. Kept as an honest negative rather than
> rewritten to look like a clean pass.

## 5. Choosing between them — and against them

| the workload is | reach for |
|---|---|
| single-key reads/writes at enormous volume, sub-ms | **Bigtable** |
| time-series, IoT telemetry, ticker data | **Bigtable** |
| documents, mobile/web clients, realtime sync, offline | **Firestore** |
| **aggregation, joins, analytics** | **BigQuery** — neither of these |
| **transactions across many rows, relational integrity** | **Cloud SQL / Spanner** |

**The two mistakes the exam keeps testing** — and both come from matching a product to data *size*
rather than *access pattern*:

1. **BigQuery as an operational store** — no cheap point lookup at high QPS.
2. **Bigtable for analytics** — no aggregation, no joins, one index.

## 6. What was actually run

| | |
|---|---|
| `01_bigtable/row_key_design.py` | ✅ against the **Bigtable emulator** |
| `02_firestore/firestore_queries.py` | ✅ against the **Firestore emulator** |
| Cloud resources | **none** — no project, no credentials, no billing |

📝 **Documented, not demonstrated:** node scaling and rebalancing, replication and app profiles,
Firestore security rules, backups, Datastore-mode differences.
