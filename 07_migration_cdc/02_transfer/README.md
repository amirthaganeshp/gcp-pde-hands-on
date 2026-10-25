# Transfer — online, offline, and the arithmetic between them

> **Domain 1 — Designing Data Processing Systems (22%)** · Success Guide p. 21 · Ultimate §1.12
> **Runtime:** <1 s · **Needs:** nothing — pure Python

```bash
python 07_migration_cdc/02_transfer/transfer_decision.py
```

Walk-through of the illustration: **[EXAMPLES.md](EXAMPLES.md)**.

---

## 1. What it is

Getting bulk data **into** Google Cloud. The exam treats this as a decision; it is mostly
**division**.

```
days = bytes / (usable bandwidth × seconds per day)
```

**Measured** (`transfer_decision.py`) — the same 100 TB:

| link | time |
|---|---|
| 100 Mbps | **132 days** |
| 1 Gbps | ~13 days |
| 10 Gbps | **1 day** |

> **Volume alone never decides this.** 100 TB is trivial on a 10 Gbps Interconnect and impossible
> on a branch-office line. The question is always *volume ÷ bandwidth*, and a question that gives
> you one without the other is incomplete.

**The crossover with Transfer Appliance: ~106 TB at 1 Gbps** (~10.6 TB at 100 Mbps). Past that,
shipping a box is faster than sending bits.

## 2. The transport options

### Online

| | bandwidth | for |
|---|---|---|
| **Public internet** | whatever you have | small, one-off |
| **Cloud VPN** | IPSec tunnel, **up to ~3 Gbps per tunnel** | small-to-medium, encrypted |
| **Partner Interconnect** | 50 Mbps – 50 Gbps | mid-size, via a service provider |
| **Dedicated Interconnect** | **10 or 100 Gbps** | continuous massive enterprise migration |

### Offline

**Transfer Appliance** — a physical storage server shipped to your data centre. Load **up to 1 PB**,
ship it back, Google uploads it into Cloud Storage. Use it when transferring over your available
bandwidth would take **weeks or months**.

## 3. The service for each job

| tool | type | when |
|---|---|---|
| **Storage Transfer Service (STS)** | online | cloud-to-cloud (**S3 / Azure → GCS**), on-prem → GCS via agents, scheduled or one-off |
| **Transfer Appliance** | offline | **20 TB+** and the network is the bottleneck |
| **BigQuery Data Transfer Service (DTS)** | managed, recurring | SaaS (Google Ads, Salesforce) and warehouses (**Redshift, Teradata, S3**) → **BigQuery** |
| **Database Migration Service (DMS)** | online | an RDBMS → Cloud SQL / AlloyDB / Spanner, minimal downtime |
| **Datastream** | online CDC | ongoing replication → BigQuery / GCS |

> **The rule that resolves most questions: Storage Transfer Service is for FILES; DMS and
> Datastream are for DATABASES.** The giveaway is whether the source is a **bucket** or an
> **engine**.

## 4. Nuances — the part worth reading

**"Usable bandwidth" is not link speed.** The link is shared with the business, TCP over a
long-haul path rarely reaches line rate, and a migration that saturates the corporate uplink is an
outage. Planning at 100% of nominal capacity is how a 13-day estimate becomes 40.

**The appliance's clock includes shipping.** Transit each way plus load and upload time — it is
not the raw copy duration. For a genuinely marginal case, the online path often wins on
*elapsed* time even when it loses on throughput.

**Offline transfer is one-shot; the source keeps changing.** An appliance captures a point in
time. Anything written while it is in transit needs a catch-up — which is CDC, and why these two
folders sit together.

**Egress from the other cloud is a real line item.** Pulling 100 TB out of S3 has an AWS bill
attached. Sometimes the correct answer is not to move it at all — see
[BigQuery Omni](../../03_bigquery/03_biglake/).

## 5. What was actually run

| | |
|---|---|
| `transfer_decision.py` | ✅ **fully executed** — arithmetic over a matrix of sizes and links |
| Cloud resources | **none** |

📝 **Documented, not demonstrated:** STS agents, the appliance workflow, Interconnect
provisioning. There is nothing to simulate — the decision *is* the arithmetic, and the arithmetic
is real.
