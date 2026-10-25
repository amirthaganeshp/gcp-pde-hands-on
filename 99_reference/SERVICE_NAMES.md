# Service names — a rename ledger

Google renames products often, and **study guides go stale silently**. A reference that confidently
uses a dead name is worse than no reference, so this file tracks what each service is called *now*,
what it used to be called, and — the part that actually matters in code — whether the API changed
with it.

> **Verified 2026-09-25** against `cloud.google.com`. Re-check before trusting this; see
> *How to verify* at the end.

---

## The rule that makes all of this survivable

**The marketing name changes. The API, CLI, client libraries and IAM roles usually do not.**

That asymmetry is why a rename breaks your *documentation* and not your *code* — and why you will
keep meeting the old name for years in `gcloud` commands, service endpoints, IAM role ids and
documentation URLs long after the console has moved on.

So: **write the new name in prose, expect the old one in code.**

## Confirmed renames

| now called | formerly | when | API / CLI / IAM |
|---|---|---|---|
| **Managed Service for Apache Spark** | **Dataproc** *and* Google Cloud Serverless for Apache Spark — **unified into one product** | recent | **unchanged** — still `dataproc.googleapis.com`, `gcloud dataproc`, docs still under `/dataproc/` |
| **Knowledge Catalog** | Dataplex Universal Catalog | **10 Apr 2026** | **unchanged** — API, client library, CLI and IAM names all stay |
| Dataplex Universal Catalog | **Data Catalog** | earlier | Data Catalog is **deprecated**; it used *tags*, the successor uses *aspects* — not a pure rename |
| **Sensitive Data Protection** | Cloud DLP / Data Loss Prevention | — | **unchanged** — still the *Cloud Data Loss Prevention API*, still `dlp.googleapis.com` |
| **Gemini Enterprise Agent Platform** | Vertex AI | Jun 2026 | **unchanged** — still `aiplatform.googleapis.com` |
| **Infrastructure Manager** | Deployment Manager | — | Deployment Manager is being wound down |

### The Managed Spark one is more than a rename

Google did not simply relabel Dataproc. It **merged two products**: Dataproc (managed clusters) and
Google Cloud Serverless for Apache Spark (zero-ops) are now one service with two deployment
models — serverless or clusters — behind a single interface.

So a question that used to be *"Dataproc or Dataproc Serverless?"* is now *"which deployment model
of Managed Service for Apache Spark?"*. The underlying trade-off is unchanged: clusters when you
need long-lived, tunable infrastructure or a specific Hadoop component; serverless when you just
want the job to run.

### The catalog lineage is three names deep

**Data Catalog → Dataplex Universal Catalog → Knowledge Catalog**, with the last hop in **April
2026**. Note this is *not* a clean rename chain: Data Catalog used **tags**, while its successors
use **aspects**, and Data Catalog itself is deprecated rather than renamed. Any material describing
"Data Catalog tags" is describing a deprecated product, not the current one under a new label.

## Names that have NOT changed (checked, so they are not re-checked)

- **Cloud Data Fusion** — still current, still receiving releases
- **Dataprep by Trifacta** — still present; **no deprecation notice found**. Now an Alteryx product
  after the Trifacta acquisition
- **Dataflow**, **Pub/Sub**, **BigQuery**, **Composer**, **Datastream**, **Bigtable**, **Spanner**,
  **Firestore**, **Cloud SQL**, **AlloyDB**, **Looker**, **Looker Studio**, **Analytics Hub**
- **Dataproc Metastore** — retains the Dataproc name even though the compute product does not

## Where this repository uses which name

| section | name used |
|---|---|
| `04_managed_spark` | **Managed Service for Apache Spark** (was `04_dataproc_spark`) |
| `10_governance_security` | **Knowledge Catalog**, **Sensitive Data Protection** |
| `09_ml_integration` | Vertex AI — see note below |

**On Vertex AI:** the PDE guides and the exam objectives still say "Vertex AI", so this repository
uses that name in exam-facing material and notes the rename rather than replacing it. Writing a
name the exam does not use would be its own kind of wrong.

## How to verify, when this file goes stale

The fastest reliable check is the product's own landing page — Google puts the old name in the
title during a transition, which is exactly the signal you want:

```
https://cloud.google.com/dataproc
  -> "Managed Service for Apache Spark (formerly Dataproc)"
```

Then confirm the API did **not** change, because that is what decides whether any code needs
touching:

```bash
gcloud services list --available | grep -i <service>
```

Check the **release notes** for a dated statement rather than trusting a blog post:
`https://docs.cloud.google.com/<product>/docs/release-notes`. That is where the 10 April 2026
Knowledge Catalog rename is recorded.

---

Sources checked 2026-09-25:
[Managed Service for Apache Spark (formerly Dataproc)](https://cloud.google.com/dataproc) ·
[Serverless overview](https://docs.cloud.google.com/dataproc-serverless/docs/overview) ·
[Knowledge Catalog release notes](https://docs.cloud.google.com/dataplex/docs/release-notes) ·
[Knowledge Catalog overview](https://docs.cloud.google.com/dataplex/docs/introduction) ·
[Sensitive Data Protection](https://cloud.google.com/security/products/sensitive-data-protection) ·
[Cloud Data Fusion](https://cloud.google.com/data-fusion)
