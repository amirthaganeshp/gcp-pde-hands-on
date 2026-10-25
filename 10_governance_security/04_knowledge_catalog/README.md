# Knowledge Catalog (formerly Dataplex Universal Catalog, and before that Data Catalog)

> **Domain 1 — Designing Data Processing Systems (22%)** · Success Guide pp. 6–9 · Ultimate §1.6
> 📝 **Write-only** — a managed governance service with no local runtime.
> **Name check:** *Data Catalog* → *Dataplex Universal Catalog* → **Knowledge Catalog** (renamed
> **10 Apr 2026**). The API, client library, CLI and IAM names did **not** change — expect
> `dataplex` in code and `datacatalog` in some IAM roles. See
> [`99_reference/SERVICE_NAMES.md`](../../99_reference/SERVICE_NAMES.md).

---

## 1. What it is

**Knowledge Catalog (formerly Dataplex Universal Catalog) is the governance layer across your whole
estate** — the data mesh service. It does four separable jobs, and the exam tests them as four:

| job | what it does |
|---|---|
| **Catalog / discovery** | The search engine for metadata across GCP. |
| **Profiling scans** | Automatic statistical shape of a dataset. |
| **Quality scans (AutoDQ)** | Rule-based validation, with pass/fail you can act on. |
| **Policy tags** | The mechanism for **column-level security**. |

## 2. Metadata model — the modern hierarchy

Recently overhauled. The old names still appear in older material, so know both:

| component | what it is | replaces |
|---|---|---|
| **Entry** | The searchable record for one physical asset — `Sales_Table_Prod`. | — |
| **Entry Group** | A logical container of entries. **Where IAM and the metadata region are set.** | — |
| **Entry Type** | A template defining what metadata a kind of asset must carry (e.g. "on-prem MySQL table"). | — |
| **Aspect Type** | A blueprint for a category of metadata — a "Compliance Info" aspect with GDPR fields. | **Tag Templates** |
| **Aspect** | The actual values attached to an entry — `GDPR_Compliant = True`. | **Tags** |
| **Glossary** | Business terminology mapped to technical assets. | — |

**Glossaries answer a specific scenario:** analysts cannot find anything because columns are named
`c_ltv_99`. A glossary maps that to *"Customer Lifetime Value"*.

## 3. Scans — profiling vs quality

| | **Data Profiling** | **Data Quality (AutoDQ)** |
|---|---|---|
| produces | statistics — min/max, **% null**, distributions, distinct counts | **pass/fail against rules** you define |
| example | "this column is 40% null" | "`order_amount` must be > 0" |
| use when | **exploring an unknown dataset** before building transformations | **monitoring pipeline health** |
| acts on failure | no — it describes | **yes** — alert, or fail the pipeline |

> **The distinction is the exam question.** *Understanding the shape of new data* → profiling.
> *Failing a pipeline when incoming data degrades* → quality scans.

## 4. Policy tags — column-level security

**This is the single most-tested thing in this topic.**

> **If a question asks how to restrict access to PII columns — SSNs, credit cards — the answer is:
> create a taxonomy of policy tags, apply the high-sensitivity tag to the column, and restrict IAM
> on that tag.**

| | |
|---|---|
| **Taxonomy** | The hierarchy of policy tags (e.g. High / Medium / Low sensitivity). |
| **Policy tag** | Attached to a **column**; access is granted via `roles/datacatalog.categoryFineGrainedReader`. |
| **Effect** | A user without the tag's role querying that column gets an error — even with full table access. |

**Why this beats authorized views at scale:** managing hundreds of views per sensitive column is an
operational nightmare. One taxonomy applied across many tables is not. Policy tags also work on
**BigLake** tables, so the same control reaches data left in GCS or S3.

## 5. Automatic discovery

Knowledge Catalog **scans Cloud Storage buckets, catalogs what it finds, and creates BigLake tables**
automatically so the data is immediately queryable in BigQuery. That is the practical bridge from
"files nobody has inventoried" to "governed, queryable assets".

## 6. Nuances — the part worth reading

**Cataloguing is not access control — except for policy tags.** Entries, aspects and glossaries
describe data; only policy tags *enforce* anything. Confusing discovery with security is the
conceptual error here.

**Metadata has a region, set at the Entry Group.** Like key rings and BigQuery datasets, this is a
placement decision made once.

**Aspect Types replaced Tag Templates**, and *Tags* became *Aspects*. Material written before the
change uses the old names throughout — including plenty of current practice exams.

**Profiling is how you find what needs tagging.** The realistic sequence is: discover → profile →
identify sensitive columns (with **Sensitive Data Protection**, next door) → apply policy tags →
restrict IAM.

## 7. What was actually run

**Nothing.** Knowledge Catalog needs a real project and real assets. The step it hands off to —
**finding and transforming sensitive data** — is measured in
[`../01_sensitive_data/`](../01_sensitive_data/), including the result that pseudonymising 50,000
identifiers preserved **100.0%** uniqueness, so it is **not** anonymisation.
