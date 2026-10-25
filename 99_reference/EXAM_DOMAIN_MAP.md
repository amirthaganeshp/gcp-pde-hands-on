# Exam domain map

The repository is organised **by service**, because that is what you can build a runnable example
for. The exam is organised **by domain**. This maps between them in both directions.

Domain weights are from the *Ultimate Comprehensive Edition* guide, which follows the official
exam blueprint. `SG` page numbers are the 117-page *Success Guide*.

---

## Domain → section

### 1. Designing Data Processing Systems — **22%**

| objective | section | SG |
|---|---|---|
| 1.1 IAM and organization policies | `10_governance_security` | 10–13 |
| 1.2 Encryption and key management | `10_governance_security` | 11 |
| 1.3 Privacy and sensitive data (DLP) | **`10_governance_security/01_sensitive_data`** ✅ | 14–17 |
| 1.4 Regional considerations, data sovereignty | `10_governance_security` | 5 |
| 1.5 Legal and regulatory compliance | `10_governance_security` | — |
| 1.6 Project/dataset/table architecture | `03_bigquery`, `08_sharing_and_viz` | 6 |
| 1.7 Multi-environment dev vs prod | `05_orchestration` | 7 |
| 1.8 Preparing and cleaning data | `02_beam_dataflow`, `03_bigquery` | 8 |
| 1.9 Monitoring and orchestration | `05_orchestration`, `11_ops_cost_monitoring` | 9 |

### 2. Ingesting and Processing the Data — **25%** *(the heaviest)*

| objective | section | SG |
|---|---|---|
| 2.1 Planning pipelines: sources, sinks, networking | `12_capstone`, `10_governance_security` | — |
| 2.2 Pub/Sub | **`01_ingestion/01_pubsub`** ✅ · **`02_kafka`** ✅ | 68–72 |
| 2.3 Real-time CDC: Datastream | **`07_migration_cdc/01_datastream`** ✅ | 27–30 |
| 2.4 Dataflow vs Managed Spark vs Dataprep | **`02_beam_dataflow`** ✅ · **`04_managed_spark`** ✅ | 73–104 |

### 3. Storing the Data — **20%**

| objective | section | SG |
|---|---|---|
| 3.1 Selecting storage systems | **`06_storage_decisions`** ✅ (tree + decision table) | 18–23 |
| 3.2 Relational deep dives | **`06_storage_decisions/05_structured_sql`** 📝 | 26–29 |
| 3.3 NoSQL deep dives | **`06_nosql/01_bigtable`** ✅ · **`02_firestore`** ✅ | 30–33 |
| 3.4 BigQuery deep dive | **`03_bigquery`** ✅ | 34–67 |

### 4. Preparing and Using Data for Analysis — **15%**

| objective | section | SG |
|---|---|---|
| 4.1 Preparing data for visualisation | **`08_sharing_and_viz/02_visualization`** 📝 | 40, 65–66 |
| 4.2 Preparing data for AI and ML | **`09_ml_integration`** 📝 | 56–62 |
| 4.3 Sharing data safely: Analytics Hub | **`08_sharing_and_viz/01_sharing`** ✅ | 45 |

### 5. Maintaining and Automating Data Workloads — **18%**

| objective | section | SG |
|---|---|---|
| 5.1 Resource and cost optimisation | **`11_ops_cost_monitoring/01_cost`** ✅ | 36–37 |
| 5.2 Automating DAGs in Composer | **`05_orchestration/01_composer`** ✅ | 105–114 |
| 5.3 BigQuery Editions and reservations | **`11_ops_cost_monitoring/01_cost`** ✅ | 36 |
| 5.4 Monitoring, alerting, observability | **`11_ops_cost_monitoring/02_monitoring`** ✅ | 115–117 |

### 6–7. Reference sections

| | |
|---|---|
| 6. CLI commands | [`CLI_REFERENCE.md`](CLI_REFERENCE.md) |
| 7. Unified pipeline architecture | **`12_capstone`** ✅ |

---

## Section → domain

| section | domains | weight served |
|---|---|---|
| `01_ingestion` | 2 | 25% |
| `02_beam_dataflow` | 2 | 25% |
| `03_bigquery` | 3, 4 | 35% |
| `04_managed_spark` | 2 | 25% |
| `05_orchestration` | 5, 1 | 18% + |
| `06_storage_decisions` | 3 | 20% |
| `07_migration_cdc` | 1, 2 | — |
| `08_sharing_and_viz` | 4 | 15% |
| `09_ml_integration` | 4 | 15% |
| `10_governance_security` | 1 | 22% |
| `11_ops_cost_monitoring` | 5 | 18% |
| `12_capstone` | all | — |

> **Legend:** ✅ has a runnable script · 📝 documented only (no honest local proxy exists).
> Every objective above now maps to a written service README; the mark says whether anything in it
> executes, not whether it is covered.

## Where the weight actually is

**Domain 2 (25%) plus domain 3 (20%) is nearly half the exam**, and both are heavily built here.
Domain 1 at 22% is the largest *single* design domain and is almost entirely configuration — which
is why `10_governance_security` is mostly write-only despite its weight.

If time is short, the ranking by *weight × how much this repo can prove* is:

1. `02_beam_dataflow` — 25%, fully runnable
2. `03_bigquery` — 35% across two domains, cost mechanics measurable
3. `01_ingestion` — 25%, fully runnable
4. `11_ops_cost_monitoring` — 18%, both halves computable
5. `06_storage_decisions` — 20%, the decision tree matters more than any one engine
