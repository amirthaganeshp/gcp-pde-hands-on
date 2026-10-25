# Visualization — Looker, Looker Studio, Connected Sheets, BI Engine

> **Domain 4 — Preparing and Using Data for Analysis (15%)** · Success Guide pp. 40, 65–66 · Ultimate §4.1
> 📝 **Write-only** — all of these are hosted products.

---

## 1. What it is

The exam does not ask you to build dashboards. It asks **which tool**, and **how to make the data
underneath fast**. Those are two separate questions and this folder answers both.

## 2. The four tools

| | what it is | choose when |
|---|---|---|
| **Looker** | **Enterprise BI with a semantic layer (LookML).** Metrics defined once, version-controlled, reused everywhere. | "**single source of truth**", governed metrics across a large org, business users exploring via curated **Explores** without SQL |
| **Looker Studio** | **Free**, web-based, drag-and-drop. **No LookML, no semantic layer.** Connects directly to hundreds of sources. | small team or startup, fast self-service, prototyping before committing engineering time |
| **Looker Studio Pro** | Looker Studio **plus** team workspaces, **scheduled report delivery**, IAM-based access. | mid-size org that wants the simple builder but needs managed access — **or when the requirement says scheduled email delivery** |
| **Connected Sheets** | **Google Sheets over BigQuery**, pivot tables and charts with **query pushdown**. | "finance/marketing want petabyte-scale analysis **but refuse to leave spreadsheets**" and lack SQL |

> **Looker and Looker Studio are completely different products that share a brand.** The
> distinguishing word in a question is almost always **governance** or **semantic layer** → Looker;
> **free / quick / ad-hoc** → Looker Studio.

**Connected Sheets is the sleeper answer.** When a scenario stresses *spreadsheet users* and
*massive data*, it is not "export a CSV" and not "build a dashboard" — the heavy lifting is pushed
down to BigQuery while the user stays in Sheets.

## 3. Making it fast — the data engineer's actual job

| lever | effect |
|---|---|
| **BI Engine** | In-memory, **sub-second**, high concurrency. **No code change** — any BigQuery client benefits. Inherits authorized views, row/column security and masking. |
| **Materialized views** | Pre-compute the aggregation; **smart tuning** reroutes base-table queries automatically. |
| **Partitioning** | Dashboard shows last quarter ⇒ partition by time so only recent partitions load into BI Engine. |
| **Denormalise / pre-aggregate** | Dashboards should read a purpose-built table, not join five raw ones at render time. |
| **Preferred tables** | Tell BI Engine which tables matter, so its memory goes there. |

**Combining materialized views with BI Engine works particularly well** — the MV joins and
flattens into a shape the in-memory layer can cache efficiently.

## 4. Nuances — the part worth reading

**A slow dashboard is almost never a dashboard problem.** It is an unpartitioned table, a
`SELECT *`, or an aggregation recomputed on every page load. The fix lives in
[`../../03_bigquery/`](../../03_bigquery/), not in the BI tool.

**BI Engine does not need a new security model** — it respects what BigQuery already enforces. That
is worth stating because a caching layer that *did* require re-implementing access control would be
a governance hazard.

**LookML is version-controlled code.** That is the actual argument for Looker: a metric definition
lives in Git, is reviewed, and cannot quietly differ between two people's dashboards. "Everyone
computes revenue slightly differently" is the problem it solves.

**Scheduled delivery is the giveaway for Looker Studio *Pro*** — the free tier does not have it.

**Prepare data *for* visualization.** Wide, flat, pre-aggregated tables at the grain the dashboard
needs. Pushing joins and window functions into render time is how a dashboard becomes both slow and
expensive — and with on-demand pricing, every refresh is billed.

## 5. What was actually run

**Nothing.** These are hosted products.

The measurable half of this section is next door in [`../01_sharing/`](../01_sharing/), where
sharing data safely was quantified: singleton groups appear at **5 dimensions** (1,288 of them),
reaching **5,056** at six — which is why an aggregation threshold, not a dashboard filter, is what
protects a shared dataset.
