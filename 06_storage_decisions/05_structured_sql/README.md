# Structured / SQL — Cloud SQL, AlloyDB, Spanner

> **Domain 3 — Storing the Data (20%)** · Success Guide pp. 26–29 · Ultimate §3.2
> 📝 **Write-only** — all three are managed services requiring a project.

---

## 1. What it is

The **transactional (OLTP)** side of the storage tree: row-oriented, ACID, indexed for point reads
and writes. BigQuery is the analytical (OLAP) counterpart, and **confusing the two is the mistake
the exam tests most often**.

| | engine | scaling | ceiling | built for |
|---|---|---|---|---|
| **Cloud SQL** | MySQL, PostgreSQL, SQL Server | **vertical** (bigger machine); read replicas scale *reads* | ~**100 TB** | ordinary OLTP — ERP, CRM, app backends |
| **AlloyDB** | PostgreSQL-compatible | hybrid; adds a **columnar engine** (HTAP) | high | high-write Postgres, **operational analytics** |
| **Spanner** | its own SQL dialect + PostgreSQL interface | **horizontal**, add nodes | **unlimited (exabytes)** | global, strongly consistent, high-ACID |

## 2. Components and mechanics

### Cloud SQL
| | |
|---|---|
| **HA** | regional, synchronous standby with automatic failover |
| **Read replicas** | asynchronous; scale reads, **not** writes |
| **Private IP** | via **Private Services Access (PSA)** — peers your VPC to Google's managed network, **no public IP at all** |
| **Backups / PITR** | automated backups plus point-in-time recovery |

### Spanner
| | |
|---|---|
| **Splits** | rows partitioned horizontally into chunks, **automatically redistributed** across nodes by load and size |
| **TrueTime** | GPS receivers + atomic clocks in Google datacentres bound clock uncertainty, giving **external consistency and serializability without locking** |
| **Interleaved tables** | physically co-locate a child table with its parent for fast joins |

### AlloyDB
| | |
|---|---|
| **Columnar engine** | keeps a column-format copy in memory so analytical queries run on the transactional database |
| **Read pools** | scale reads horizontally |

## 3. Nuances — the part worth reading

**"Relational" is not the deciding word — *scale* and *geography* are.**

| the scenario says | answer |
|---|---|
| relational, single region, normal size | **Cloud SQL** |
| relational + **global** + strong consistency | **Spanner** |
| relational + **PostgreSQL** + analytics on the live data | **AlloyDB** |
| "unlimited horizontal scale" + relational + ACID | **Spanner** |
| analytical scans over history | **BigQuery** — not this family at all |

**Spanner is the answer to a specific pair of words: *global* and *ACID*.** It is expensive and
over-specified for a single-region application; it is the only option when the requirement is
worldwide strong consistency.

**Read replicas do not scale writes.** A Cloud SQL write bottleneck is solved by a bigger instance
(vertical), by sharding at the application layer, or by moving to Spanner — never by adding
replicas.

**Hot-spotting applies here too.** Monotonically increasing primary keys (auto-increment,
timestamp) concentrate writes on one Spanner split, exactly as they do on a
[Bigtable row key](../06_nosql/01_bigtable/) — where this repo **measures** the effect at
**1.0 of 8** tablets vs **7.9**. Use UUIDs or hash-prefixed keys.

**Cloud SQL's ~100 TB ceiling is a real exam fact.** A scenario describing growth past it is
signalling Spanner.

## 4. Where these sit in a data pipeline

Usually as the **source**, not the destination:

- **Datastream** reads their change logs for near-real-time CDC → BigQuery.
- **DMS** migrates them into Cloud SQL/AlloyDB/Spanner with minimal downtime.
- **Federated queries** let BigQuery read Cloud SQL directly for small lookups.
- **Never** point analytical dashboards at the production OLTP database — that is what the
  warehouse is for.

## 5. What was actually run

**Nothing.** These are managed services. Their **CDC output** is what this repo demonstrates, in
[`../../07_migration_cdc/`](../../07_migration_cdc/) — LSN ordering, tombstones, and a naive merge
producing **464 rows against a truth of 461**.
