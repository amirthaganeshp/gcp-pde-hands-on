# Cloud Dataprep

> **Domain 2 — Ingesting and Processing (25%)** · Success Guide §11.5.x · Ultimate §2.4
> 📝 **Write-only** — a managed partner UI service with no local runtime.

---

## 1. What it is

A **serverless, visual data-preparation service** (built with Alteryx/Trifacta) for exploring,
cleaning and reshaping messy datasets **without writing code** — a spreadsheet-like grid rather
than a pipeline canvas.

**Its defining architectural property is pushdown.** Dataprep does not process your data itself.
It translates your visual logic and **pushes execution down to BigQuery** (SQL-shaped work) or
**Dataflow** (complex parsing). You manage no infrastructure at all.

## 2. Components

| component | what it is |
|---|---|
| **Flow** | The organisational container — datasets + recipes + outputs as one visual graph, showing **lineage**. |
| **Recipe** | The ordered transformation steps, in a human-readable DSL. Editable, versionable, parameterisable, exportable. |
| **Sample** | The subset you build the recipe against — see below. |
| **Profile** | Automatic column histograms, type inference and **colour-coded quality flags** (missing, mismatched, outliers) generated on import. |
| **Predictive transformation** | Highlight a pattern and Dataprep infers the intent, suggesting the transform in one click. |

## 3. Sampling — the part the exam actually tests

Building a recipe against 10 TB interactively would be unusable, so you build against a **sample**
and then run the finished recipe across the **full** dataset in BigQuery or Dataflow.

| sample | what it does | when |
|---|---|---|
| **Initial (first N)** | first rows (~10 MB) on import | instant start — **but if the file is sorted or grouped, it is not representative** |
| **Random** | random rows across the whole dataset | an unbiased cross-section for general recipes |
| **Stratified** | proportionate sample per value of a column | **imbalanced data** — guarantees the 1% fraud class appears |
| **Anomaly / mismatch** | only rows with errors, type mismatches, nulls | troubleshooting dirty records, building validation/DLQ logic |
| **Filtered** | rows matching a custom condition | isolating one region or year from an enterprise dataset |

**The initial-sample trap is the exam's favourite here:** chronologically sorted input makes the
first 10,000 rows a poor proxy for the whole file, and a recipe built on it silently fails on the
rest.

## 4. Nuances — the part worth reading

**Pushdown means Dataprep's cost is BigQuery's or Dataflow's cost.** "Serverless" describes the
interface, not the bill.

**A recipe is an artifact, not a click-trail.** It can be parameterised and reapplied to recurring
datasets, which is what separates this from ad-hoc manual cleanup in a spreadsheet.

**The sample is not the data.** Every transformation you see succeed was verified against a subset.
Running on the full dataset is a distinct step and can surface values the sample never contained.

## 5. Dataprep vs Data Fusion

| | **Dataprep** | **Data Fusion** |
|---|---|---|
| interface | spreadsheet-like grid, **AI-suggested transforms** | node-based pipeline canvas |
| purpose | **interactive wrangling and exploration** | **repeatable production ETL** |
| runs on | BigQuery / Dataflow (pushdown) | Dataproc |

> If the question mentions **smart, suggested transformations inside a spreadsheet-like grid**,
> it is Dataprep. If it mentions a **node-based pipeline canvas** for scheduled production ETL,
> it is Data Fusion.

## 6. When to use it — and when not

**Use it when** an analyst or scientist must visually explore an unfamiliar, messy dataset, fix
quality issues, and pivot or join quickly.

**Don't** when you need a governed, version-controlled, scheduled production pipeline (Data Fusion
or Dataform), or genuine stream processing (Dataflow).

## 7. What was actually run

**Nothing.** There is no local Dataprep. The **engines it pushes down to** are covered here:
[`../../03_bigquery/`](../../03_bigquery/) and [`../../02_beam_dataflow/`](../../02_beam_dataflow/).
