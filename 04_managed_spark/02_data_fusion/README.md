# Cloud Data Fusion

> **Domain 2 — Ingesting and Processing (25%)** · Success Guide §11.5.x · Ultimate §2.4
> 📝 **Write-only** — a managed UI service with no local runtime.

---

## 1. What it is

A **code-free, visual ETL/ELT builder** for enterprise data engineers and analysts, built on the
open-source **CDAP** project. You assemble pipelines on a node-based canvas from a library of
connectors and transforms.

**It is not a different engine.** Data Fusion **compiles your visual pipeline into a Dataproc job**
and runs it there. The canvas is the interface, not the runtime.

## 2. Components

| component | what it is |
|---|---|
| **Studio / canvas** | The node-based pipeline designer — sources, transforms, sinks. |
| **Wrangler** | Interactive, spreadsheet-like cleaning that produces a **recipe**. |
| **Recipe** | The ordered list of transformation steps Wrangler generates. |
| **Macros** | **Runtime parameters** — `${table_name}`, `${date}`. |
| **Plugins / connectors** | Out-of-the-box connectors to enterprise sources (databases, SaaS, mainframe, Salesforce…). |
| **Hub** | Where reusable plugins, pipelines and templates are shared. |
| **Editions** | Developer · Basic · Enterprise — Enterprise adds streaming and HA. |

## 3. Fundamental operations

1. Pick a source plugin and a sink plugin; wire transforms between them.
2. Clean interactively in **Wrangler**; the recipe becomes a pipeline node.
3. Parameterise with **macros** so one pipeline serves many tables or dates.
4. Deploy; Data Fusion provisions a **Dataproc** cluster and runs it.
5. Inspect lineage — Data Fusion tracks **field-level lineage** automatically.

## 4. Nuances — the part worth reading

**Macros are the answer to a specific exam question.** If asked how one pipeline can process
different tables or date paths *without redesigning the layout* — that is **macros**, and nothing
else in the product does it.

**Wrangler recipes answer the other one:** ad-hoc visual cleaning *before* mapping data into an
ETL workflow.

**It runs on Dataproc, so it inherits Dataproc's cost model.** A Data Fusion pipeline is not
serverless in the Dataflow sense — an ephemeral cluster is provisioned per run.

**The exam trap:** a question asking for **serverless stream processing with custom code and
complex windowing** is **Dataflow**, not Data Fusion — no matter how much the phrase "visual
pipeline" appears.

## 5. Data Fusion vs Dataprep vs Dataflow

| | **Data Fusion** | **Dataprep** | **Dataflow** |
|---|---|---|---|
| shape | node-based canvas | spreadsheet-like grid | code (Beam) |
| for | **repeatable production ETL** | **interactive wrangling/exploration** | any pipeline, batch + stream |
| audience | data engineers, analysts | analysts, scientists | engineers |
| runs on | Dataproc | BigQuery **or** Dataflow (pushdown) | Dataflow |

**Data Fusion builds scheduled production systems; Dataprep explores a messy file.**

## 6. When to use it — and when not

**Use it when** the requirement explicitly says *code-free / visual* for repeatable enterprise ETL,
or when you need native connectors to enterprise sources without writing API code.

**Don't** when the pipeline needs custom streaming logic, windowing, or anything genuinely
programmatic — that is Dataflow.

## 7. What was actually run

**Nothing.** Data Fusion is a managed UI over Dataproc with no local equivalent. The **Dataproc
execution layer underneath it** is what this section demonstrates, in
[`../01_spark/`](../01_spark/).
