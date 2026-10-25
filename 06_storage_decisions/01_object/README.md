# Cloud Storage — the class decision

> **Domain 3 (20%)** · Success Guide pp. 18–23 · Ultimate §3.1 · **Runtime:** <1 s

```bash
python 06_storage_decisions/01_object/storage_class_cost.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

---

## 1. What it is

Object storage: buckets, objects, and no query engine. Eleven nines of durability, a flat
namespace, and four **storage classes** that differ only in price shape.

## 2. Components

| component | what it is |
|---|---|
| **Bucket** | The unit of location, class default, IAM and lifecycle. |
| **Object** | An immutable blob. "Renaming" is copy + delete. |
| **Storage class** | Standard / Nearline / Coldline / Archive. Set per bucket *or* per object. |
| **Lifecycle rule** | Transition or delete by age, class, or version count. |
| **Autoclass** | Moves objects between classes based on real access. |
| **Versioning** | Keeps noncurrent versions — **which are still billed**. |
| **Retention policy** | Blocks deletion, including by lifecycle rules. |

**"Folders" do not exist.** Object names contain `/` and the console renders it as a tree.

## 3. The four classes

| class | $/GB/mo | $/GB retrieved | min duration |
|---|---|---|---|
| Standard | 0.0260 | 0.000 | none |
| Nearline | 0.0100 | 0.010 | 30 days |
| Coldline | 0.0040 | 0.020 | 90 days |
| Archive | 0.0012 | 0.050 | 365 days |

*Approximate US multi-region list prices. They move — re-check before quoting them.*

**All four have identical durability, API and first-byte latency.** Archive is not tape and there
is no thaw delay — a misconception carried over from other clouds.

## 4. Nuances — the part worth reading

**The class is a crossover, not a preference.** Computed:

| pair | crosses at |
|---|---|
| Standard vs Nearline | **1.60 reads/month** |
| Nearline vs Coldline | 0.60 reads/month |
| Coldline vs Archive | 0.09 reads/month |

Below the crossover the colder class wins; above it, the warmer one does. **Standard beats Nearline
once the data is read more than 1.6 times a month** — which for anything a dashboard touches is
every day.

1 TB read once a month: Nearline $20.48, Coldline $24.58, **Archive $52.43** — twice the price of
Standard. Reasoning from the storage price alone gets this exactly backwards.

**The minimum-duration trap is the expensive one.** Delete early and you still pay the minimum:

| deleted after | Standard | Archive |
|---|---|---|
| **1 day** | **$0.89** | **$14.95** |
| 30 days | $26.62 | $14.95 |
| 365 days | $323.93 | $14.95 |

**For one day of 1 TB, Archive costs 17× more than Standard** — the full 365-day minimum. The
early-deletion charge also applies to **overwrites and class changes**, not just deletes, which is
what makes an aggressive lifecycle policy expensive: transition to Archive at 30 days and delete at
90, and you pay the full year on every object.

**Autoclass avoids that** — it moves objects on real access with no early-deletion charge on its
own transitions, for a small per-object fee. Predictable ageing → lifecycle rules. Unpredictable or
mixed → Autoclass. Many tiny objects → watch the per-object fee.

**Versioning bills for noncurrent versions forever** unless a lifecycle rule on noncurrent versions
removes them.

**A locked retention policy cannot be shortened or removed by anyone**, including the project
owner. That is the point of it, and it is not reversible.

## 5. Data protection and retention

| feature | what it does | the detail that gets tested |
|---|---|---|
| **Versioning** | An overwrite creates a new version; the old becomes **noncurrent**. | Noncurrent versions are **still billed** — add a lifecycle rule on them. |
| **Soft delete** | Deleted/overwritten objects are kept hidden and restorable. | **On by default, 7 days**, configurable **up to 90**. |
| **Retention policy / Bucket Lock** | Enforces **WORM** — "retain 7 years". | Once **locked**, *nobody* can delete or shorten it — not the owner, not Google. |
| **Object Retention Lock** | The same, per object. | Finer-grained WORM. |
| **Object hold** | A temporary freeze on deletion. | **Overrides lifecycle rules** — the legal-hold answer. |

### Lifecycle rule precedence — the destructive action wins

Rules are evaluated **independently and in parallel**, so two reasonable-looking rules combine
badly:

```
Rule 1: move to Coldline after 30 days
Rule 2: delete after 30 days
Result: DELETED at 30 days. The delete wins.
```

> This is the exam's favourite Cloud Storage trap, and it is a genuine production hazard: neither
> rule is wrong on its own, and nothing warns you.

## 6. Capabilities worth recognising by keyword

| feature | the scenario that means it |
|---|---|
| **GCS FUSE** | "legacy app must `open('/mnt/gcs/file.txt')` and **cannot be modified**" |
| **Requester Pays** | "we publish large public datasets but **users should pay the egress**" |
| **Dual-region bucket** | "high availability and geo-redundancy across **two specific linked regions**" |
| **Parallel composite uploads** | "speed up **multi-gigabyte** single-file uploads" |
| **Autoclass** | "access patterns are **unpredictable**" |

> **FUSE is a compatibility shim, not a filesystem.** GCS is not POSIX: FUSE is slow, and wrong for
> high-performance computing, small random I/O, or several writers on one object. Those need
> [Filestore](../03_file/). Reach for FUSE only when the application genuinely cannot be changed.

## 7. When to use it — and when not

| situation | reach for |
|---|---|
| blobs, files, backups, a data lake | **Cloud Storage** |
| tabular data you will query | **BigQuery**, or an external table over GCS |
| a POSIX filesystem several VMs mount | **Filestore** |
| a disk for one VM | **Persistent Disk** |
| frequent small appends | not object storage — objects are immutable |

## 8. What was actually run

| | |
|---|---|
| `storage_class_cost.py` | ✅ **fully executed** — pure arithmetic |
| Cloud resources | **none** |

The **method** is the deliverable; the prices are approximate list prices that move and differ by
region. Re-run it with current numbers rather than trusting these digits.
