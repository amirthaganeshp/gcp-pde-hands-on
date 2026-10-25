# Sharing and visualisation

> **Domain 4 — Preparing and Using Data for Analysis (15%)** · Success Guide pp. 40, 45, 65–66 ·
> Ultimate §4.1, §4.3

| service | covers | state |
|---|---|---|
| [`01_sharing/`](01_sharing/) | Analytics Hub, clean rooms, authorised views, policy tags | ✅ built |
| [`02_visualization/`](02_visualization/) | Looker vs Looker Studio vs Pro vs Connected Sheets, BI Engine | 📝 documented |

---

## Two questions, often confused

**Who may see this?** — [`01_sharing/`](01_sharing/). Sharing without copying, and why
"we only publish aggregates" is not a privacy control: measured, singletons appear at **five**
quasi-identifiers and reach **36% of all groups** at six.

**Why is the dashboard slow?** — usually a modelling problem rather than a tool problem.
Pre-aggregate, use a materialized view, or put BI Engine in front. A dashboard issuing a full-scan
query per tile is not fixed by changing dashboard tools.

## Looker or Looker Studio?

| | **Looker** | **Looker Studio** |
|---|---|---|
| model | **LookML** — a governed semantic layer | ad hoc, per report |
| metric definitions | defined once, centrally | redefined in each report |
| cost | licensed | free (Pro adds support and admin) |
| use when | metrics must agree across the org | someone needs a chart today |

**The exam's angle is governance.** "Different teams report different revenue numbers" is a LookML
answer — one definition, reused — not a Looker Studio one.

**Connected Sheets** is the answer when the business will not leave the spreadsheet: it queries
BigQuery directly from Sheets, with no export and no row limit.

## Preparing data *for* visualisation

The §4.1 objective, and the thing most dashboard problems actually are:

| symptom | fix |
|---|---|
| every tile scans the base table | **pre-aggregate** into a reporting table |
| the aggregate is stale or expensive to maintain | **materialized view** — incremental, auto-refreshed |
| sub-second interactivity needed | **BI Engine** — in-memory acceleration |
| filters are slow | partition and cluster on the filter columns |
| the join is the slow part | denormalise into a wide table |

BI Engine is acceleration, not a fix for a bad model. It has a size limit and a cost, and it will
happily make a badly-modelled query slightly less slow.
