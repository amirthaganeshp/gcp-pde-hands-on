# File storage — Filestore

> **Domain 3 — Storing the Data (20%)** · Success Guide pp. 18–20 · Ultimate §3.1
> 📝 **Write-only** — a managed NFS service; nothing to run locally.

---

## 1. What it is

**Managed NFS.** A shared filesystem that **many VMs mount at once**, with POSIX semantics —
directories, file locking, partial writes, rename-as-atomic.

That last point is the entire reason it exists. Object storage has none of those things.

## 2. The tiers

| tier | for |
|---|---|
| **Basic** (HDD / SSD) | general file sharing, dev environments |
| **Zonal** | higher performance, single zone |
| **Regional** | zonal performance plus regional availability |
| **Enterprise** | highest availability, snapshots, GKE-friendly |

Also in this space: **NetApp Volumes** (multi-protocol, NFS + SMB) when Windows clients or
enterprise NAS features are required.

## 3. Nuances — the part worth reading

**The decision is POSIX semantics, not "files".** Cloud Storage also stores files. What it cannot
give you is:

| Filestore has | Cloud Storage does not |
|---|---|
| file **locking** | — |
| **partial/in-place writes** | objects are immutable; you rewrite the whole thing |
| real **directories** | prefixes that *look* like directories |
| atomic **rename** | copy + delete, non-atomic |
| **`open()`/`seek()`** from unmodified software | an API, or a FUSE layer with caveats |

**So the honest test is: "does the application refuse to be changed?"** Legacy analytics software,
rendering pipelines and HPC jobs that assume a mounted filesystem are the real use cases. If you
control the code, object storage is cheaper and scales further.

**Capacity is provisioned, not elastic.** You choose a size and pay for it whether it is full or
empty — the opposite of Cloud Storage's pay-for-what-you-store. A Filestore instance sitting at 5%
utilisation is pure waste, and there is no lifecycle policy to save you.

**It is not a data lake.** No storage classes, no lifecycle transitions, no archive tier, no
BigQuery external tables over it.

## 4. When to use it — and when not

| situation | reach for |
|---|---|
| several VMs need the **same mounted filesystem** | **Filestore** |
| lift-and-shift of software that requires POSIX | **Filestore** |
| GKE workloads needing `ReadWriteMany` volumes | **Filestore** |
| NFS **and** SMB, or enterprise NAS features | **NetApp Volumes** |
| **analytics input, a data lake, pipeline staging** | **Cloud Storage** |
| one VM's own disk | **Persistent Disk** |
| analytical queries | **BigQuery** |

> **In a PDE question, Filestore is usually the distractor.** Data-engineering pipelines read and
> write object storage. Filestore appears when the scenario is explicitly about **shared POSIX
> access from multiple machines** — and if that phrase is absent, it is not the answer.

## 5. What was actually run

**Nothing.** Filestore is a managed NFS instance with no local equivalent worth pretending about.
The storage classification tree is in [`../README.md`](../README.md).
