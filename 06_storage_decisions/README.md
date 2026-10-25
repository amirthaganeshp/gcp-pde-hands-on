# Storage decisions

> **Domain 3 — Storing the Data (20%)** · Success Guide pp. 18–33 · Ultimate §3.1–3.3

*"Which storage service?"* is the commonest shape of PDE question, and the answer comes from
placing the workload in the tree before comparing products.

```
                         ┌─ 01_object       blobs, no query engine
    by STORAGE TYPE ─────┼─ 02_block        disks attached to a VM
                         ├─ 03_file         a shared POSIX mount
                         └─ 04_in_memory    microsecond reads, volatile

    by DATA MODEL ───────┬─ 05_structured_sql   schema + joins + transactions
                         └─ 06_nosql            schema-flexible, horizontal scale
```

> NoSQL stores are **semi-structured**, not unstructured. A Bigtable row and a Firestore document
> have plenty of structure — what they lack is a *fixed, enforced* schema and SQL joins. Genuinely
> unstructured data is an object in Cloud Storage.

| branch | services | state |
|---|---|---|
| [`01_object/`](01_object/) | Cloud Storage — classes, lifecycle, the cost crossover | ✅ built |
| [`02_block/`](02_block/) | Local SSD's ephemerality, PD tiers, Hyperdisk | 📝 documented |
| [`03_file/`](03_file/) | Filestore — when POSIX semantics are the requirement | 📝 documented |
| [`04_in_memory/`](04_in_memory/) | Memorystore — cache-aside, TTL, eviction | ✅ built |
| [`05_structured_sql/`](05_structured_sql/) | Cloud SQL, AlloyDB, Spanner — splits and TrueTime | 📝 documented |
| [`06_nosql/`](06_nosql/) | **NoSQL overview** — the relational→Firestore vocabulary map, Bigtable's data model | 📝 documented |
| [`06_nosql/01_bigtable/`](06_nosql/01_bigtable/) | **Bigtable row-key design** | ✅ built |
| [`06_nosql/02_firestore/`](06_nosql/02_firestore/) | documents, composite indexes, query limits | ✅ built |

---

## The decision table

| if the workload is... | reach for | because |
|---|---|---|
| analytical scans, aggregation, SQL | **BigQuery** | separates storage from compute |
| point reads/writes by key, huge scale | **Bigtable** | one sorted index, millisecond reads |
| relational, single region, familiar | **Cloud SQL** | managed MySQL/Postgres/SQL Server |
| relational + HTAP + read pools | **AlloyDB** | Postgres-compatible, columnar engine |
| relational + **horizontal scale + global** | **Spanner** | TrueTime, external consistency |
| documents, mobile/web sync | **Firestore** | offline sync, realtime listeners |
| blobs, files, archives, data lake | **Cloud Storage** | classes from Standard to Archive |
| a cache, or a session store | **Memorystore** | microseconds, and **volatile** |
| a POSIX filesystem several VMs mount | **Filestore** | when object semantics genuinely will not do |

## The two mistakes the exam keeps testing

**BigQuery as an operational store.** No cheap point lookup, no useful per-row latency. A key-value
workload belongs in Bigtable. *"Millions of reads per second by user id"* is never BigQuery.

**Bigtable for analytics.** No aggregation, no joins, no secondary index. *"Ad-hoc analysis across
the whole dataset"* is never Bigtable.

Both are the same error: matching a product to data *size* rather than to the **access pattern**.

## The finding that generalises

[`06_nosql/01_bigtable/`](06_nosql/01_bigtable/) measures four row-key designs. A timestamp-first
key reached **1.0 of 8 tablets per write burst**; promoting the station field to the front reached
**7.9**. Same data, same rows, one design decision.

That is the same failure as a **Kafka hot partition** and a **Spark skewed key** — one key, one
worker, no parallelism — showing up in a third service. Worth recognising by shape rather than
memorising three times.
