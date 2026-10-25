# Migration and CDC

> **Domains 1 + 2** · Success Guide pp. 21–22, 27–30 · Ultimate §2.1, §2.3

| service | covers | state |
|---|---|---|
| [`01_datastream/`](01_datastream/) | **CDC semantics** — change log to current state | ✅ built |
| [`02_transfer/`](02_transfer/) | **online vs appliance**, and which transfer service | ✅ built |
| [`03_dms/`](03_dms/) | homogeneous vs heterogeneous, the four phases, promote | 📝 documented |

---

## The two questions this section answers

**1. How do you move the data at all?** Arithmetic, not judgement — see
[`02_transfer/`](02_transfer/). The same 100 TB takes **132 days** on a 100 Mbps link and **1 day**
on a 10 Gbps one. The size never decides it on its own.

**2. How do you keep the source running while you move?** That is CDC, and the hard part is not
capturing the changes — it is applying them correctly. See [`01_datastream/`](01_datastream/).

## The minimal-downtime migration, in four phases

Every "migrate with minimal downtime" question is this shape:

```
1. ASSESS & CONVERT   schema differences, unsupported types, the things
                      that will not translate
2. BULK LOAD          a snapshot of the source, while it keeps serving
3. CDC CATCH-UP       stream changes since the snapshot until the lag is
                      small - this is the phase that makes the downtime
                      short instead of long
4. PROMOTE & CUTOVER  stop writes, let the lag drain, repoint the app
```

**Homogeneous** (MySQL → Cloud SQL for MySQL) skips most of phase 1. **Heterogeneous**
(Oracle → PostgreSQL) is mostly phase 1 — the conversion is the project, and the replication is the
easy part.

## DMS or Datastream?

Both read a live database's change log. They are for opposite intentions:

| | **Database Migration Service** | **Datastream** |
|---|---|---|
| goal | **migrate** and stop using the source | **replicate** and keep both |
| ends? | yes, at cutover | no, it is ongoing |
| schema conversion | yes | no |
| typical target | Cloud SQL, AlloyDB | BigQuery, GCS |

**Storage Transfer Service is for FILES; DMS and Datastream are for DATABASES.** Confusing them is
the commonest wrong answer, and the giveaway is whether the source is a bucket or an engine.
