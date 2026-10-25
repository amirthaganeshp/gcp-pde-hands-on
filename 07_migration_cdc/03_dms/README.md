# Database Migration Service (DMS)

> **Domain 1 — Designing Data Processing Systems (22%)** · Success Guide p. 22 · Ultimate §1.12
> 📝 **Write-only** — a managed service; nothing to run locally.

---

## 1. What it is

**Serverless database migration with minimal downtime.** DMS lifts a running database engine into
Cloud SQL, AlloyDB or Spanner using **continuous logical replication**, so the source keeps serving
until the moment you cut over.

**The defining difference from Datastream: DMS ends.** It exists to make the source redundant.
Datastream is designed to run forever.

| | |
|---|---|
| **Sources** | MySQL, PostgreSQL, Oracle, SQL Server (on-prem, GCE, other clouds) |
| **Targets** | Cloud SQL, AlloyDB, Spanner |
| **Method** | snapshot + continuous replication, then **promote** |

## 2. Components

| component | what it is |
|---|---|
| **Connection profile** | Source credentials and connectivity. |
| **Migration job** | One source → one target, `one-time` or `continuous`. |
| **Conversion workspace** | **Heterogeneous only** — where schema conversion happens and is edited. |
| **Promote** | **The cutover.** Ends replication and makes the destination authoritative. |

## 3. Homogeneous vs heterogeneous

| | **homogeneous** | **heterogeneous** |
|---|---|---|
| example | MySQL → Cloud SQL for MySQL | **Oracle → PostgreSQL** |
| schema conversion | none needed | **the entire project** |
| hard part | connectivity and cutover timing | stored procedures, data types, dialect |
| DMS role | does nearly all of it | does the replication; conversion needs review |

> **Heterogeneous migration is a code-conversion project with a replication step attached**, not a
> replication project. `PL/SQL` → `PL/pgSQL`, `NUMBER` → `NUMERIC`, sequences, triggers, and
> Oracle-specific functions all need human attention. DMS surfaces them; it does not decide them.

## 4. The four phases

```
1. ASSESS & CONVERT   conversion workspace flags what will not translate
2. BULK LOAD          initial snapshot, source still serving
3. CDC CATCH-UP       replicate changes until replication lag is small
                      - this phase is what makes the downtime short
4. PROMOTE            stop writes, let lag drain to zero, repoint the app
```

**Downtime is phase 4 only**, and only as long as it takes the remaining lag to drain. That is the
entire argument for this shape over export-and-import.

## 5. Nuances — the part worth reading

**`promote` is irreversible in practice.** It ends replication and makes the target authoritative.
There is no "un-promote" — the rollback plan is repointing the application at the old source, which
only works if nothing has been written to the new one yet.

**Connectivity is the usual blocker**, not the data. DMS needs to reach the source: VPC peering,
Cloud VPN, Interconnect, or an SSH tunnel, plus firewall rules and a replication user with the
right grants.

**The source must be configured for logical replication** before anything works — `binlog_format
= ROW` for MySQL, `wal_level = logical` plus replication slots for PostgreSQL, supplemental logging
for Oracle. This is a change to the production database, and it usually needs a maintenance window
of its own.

**Verify before promoting.** Row counts per table, checksums on critical tables, and a replication
lag of ~0. Promotion is the point after which comparison against the source stops being
meaningful.

## 6. DMS vs Datastream vs DTS

| | **DMS** | **Datastream** | **DTS** |
|---|---|---|---|
| intent | **migrate and stop** | **replicate and keep** | **scheduled loads** |
| converts schema | **yes** | no | no |
| target | Cloud SQL, AlloyDB, Spanner | BigQuery, GCS | BigQuery |
| ends | at promotion | never | recurring |

## 7. What was actually run

**Nothing.** DMS requires a real source database and a real target instance. The **CDC semantics**
underneath phase 3 — LSN ordering, tombstones, idempotent merge — are demonstrated and measured in
[`../01_datastream/`](../01_datastream/), where a naive merge produced **464 rows against a truth
of 461**.
