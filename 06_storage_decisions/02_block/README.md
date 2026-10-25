# Block storage — Persistent Disk, Local SSD, Hyperdisk

> **Domain 3 — Storing the Data (20%)** · Success Guide pp. 18–20 · Ultimate §3.1
> 📝 **Write-only** — block devices attach to VMs; there is nothing to run locally.

---

## 1. What it is

**Raw block devices attached to a Compute Engine VM.** The VM's operating system puts a
filesystem on them. One disk, one VM (with narrow read-only exceptions).

**Block storage barely appears on the PDE exam as a *destination*.** It matters for one reason:
knowing when the answer is **not** block storage. A data engineer reaching for a Persistent Disk to
hold a data lake has made the mistake the exam is testing.

## 2. The options

| | attached how | durability | use for |
|---|---|---|---|
| **Local SSD** | **physically to the host** | **EPHEMERAL — data is lost if the VM stops, is deleted, or the host fails** | scratch, swap, **shuffle spill**, a cache tier |
| **Standard PD** (pd-standard) | network | durable, replicated | cheap cold sequential — backups |
| **Balanced PD** (pd-balanced) | network | durable | the sensible default for boot + general workloads |
| **SSD PD** (pd-ssd) | network | durable | operational databases, high IOPS |
| **Hyperdisk** | network | durable | **IOPS and throughput scale independently of capacity** |

**Hyperdisk is the one worth remembering by name**: with every other type, buying more performance
means buying more gigabytes you don't need.

## 3. Nuances — the part worth reading

**"Ephemeral" means exactly that.** Local SSD survives a reboot; it does **not** survive a stop, a
delete, or a host failure. Anything on it must be reproducible. This is why Dataproc uses local
SSD for *shuffle* data and Cloud Storage for *results*.

**Performance scales with size on PD.** A 10 GB pd-balanced gets a small IOPS allocation; the same
disk at 1 TB gets far more. A "slow disk" is frequently just a small one — which is precisely the
coupling Hyperdisk removes.

**Persistent Disk is zonal (or regional) and attaches to one VM.** If several machines need the
same files, block storage is the wrong layer — that is [Filestore](../03_file/), or more often
object storage.

## 4. Where this actually shows up in a data pipeline

| situation | the block-storage angle |
|---|---|
| **Dataflow workers** | `--disk_size_gb`, `--worker_disk_type=pd-ssd` — only matters when **not** using service-side shuffle |
| **Dataproc** | local SSD for shuffle spill; **HDFS on PD is the anti-pattern** — permanent data belongs in GCS |
| **Self-managed databases on GCE** | SSD PD or Hyperdisk |
| **Kafka on GKE/GCE** | the log lives on block storage; this is part of the operational cost Pub/Sub removes |

## 5. When to use it — and when not

| you need | use |
|---|---|
| a filesystem for one VM | **Persistent Disk** |
| the fastest possible scratch, and can lose it | **Local SSD** |
| high IOPS without buying capacity | **Hyperdisk** |
| **a data lake, analytics input, anything shared** | **Cloud Storage** — not block |
| **a POSIX mount shared by many VMs** | **Filestore** |
| **an analytical warehouse** | **BigQuery** |

> **The exam's framing:** block storage is *infrastructure under* a workload, never the storage
> *decision* for data. If a question offers Persistent Disk alongside Cloud Storage, BigQuery and
> Bigtable for a data-engineering problem, PD is a distractor.

## 6. What was actually run

**Nothing.** Block storage requires a VM. The classification tree this folder sits in — object vs
block vs file vs in-memory vs SQL vs NoSQL — is in
[`../README.md`](../README.md); the measurable parts of it are
[`../01_object/`](../01_object/) and [`../04_in_memory/`](../04_in_memory/).
