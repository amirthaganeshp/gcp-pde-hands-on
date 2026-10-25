# ML integration

> **Domain 4 — Preparing and Using Data for Analysis (15%)** · Success Guide pp. 56–62 ·
> Ultimate §4.2

**This section is deliberately thin, and says so.** The
companion [`gcp-ml-hands-on`](https://github.com/amirthaganeshp/gcp-ml-hands-on) repository covers ML
properly — six phases, every number measured. Duplicating it here would produce a second copy that
rots. This section covers only what a **data engineer** is asked about.

| service | covers | state |
|---|---|---|
| [`01_bigquery_ml/`](01_bigquery_ml/) | model types, **data splitting**, leakage, `TRANSFORM` | 📝 documented (SQL written, never submitted) |
| [`02_vertex_ai/`](02_vertex_ai/) | pretrained/AutoML/custom, Feature Store, splits and leakage, RAG | 📝 documented |

---

## The PDE exam does not ask you to build models

It asks whether the **data engineering around them** is right:

- where does the model run, and does the data have to move?
- how is the data split, and does that split leak the future?
- are any features unavailable at prediction time?
- is the same preprocessing applied at training and at serving?

All four are data-engineering failures. None of them are modelling.

## The decision

| if... | then |
|---|---|
| the data is in BigQuery and the model is standard | **BigQuery ML** — the data never moves |
| univariate/multi-series forecasting | **`ARIMA_PLUS`** — one statement, thousands of series |
| you already have a trained TF/ONNX model | **import it into BQML**, or a **remote model** |
| custom architecture, custom loss, GPUs | **Vertex AI custom training** |
| a user is waiting, sub-second | **Vertex endpoint** — `ML.PREDICT` is batch only |
| predictions once a day into a table | **`ML.PREDICT`** — no endpoint, no node-hours |

**BQML's pitch is that the data never moves** — no export, no training infrastructure, no serving
system. Its limit is that it is batch, and its model catalogue is deliberately narrow.

## The two facts most worth carrying

**`AUTO_SPLIT` is the default and its behaviour changes with row count:**

| rows | what happens |
|---|---|
| **< 500** | **all rows train. There is no evaluation set at all.** |
| 500 – 50,000 | 80% train / 20% eval, **random** |
| > 50,000 | 10,000 rows eval, rest train, **random** |

Under 500 rows, `ML.EVALUATE` reports performance on data the model trained on. The number looks
excellent and means nothing, and nothing warns you.

**The split is random, which leaks the future on time-ordered data.** Use `DATA_SPLIT_METHOD='SEQ'`
with a date column, or `CUSTOM` with your own flag. The ML repo measured exactly this failure:
a random split on a time series made the error look **2× better** than it was.

## Cross-links, rather than copies

| topic | where it is done properly |
|---|---|
| train/test splits, and why random leaks | `01_foundations/05_data_leakage` |
| ROC vs PR, calibration, metric choice | `01_foundations/04_roc_vs_pr_curves` |
| when a GBM beats a neural net on tabular data | `02_traditional_ml/01_regression` |
| Vertex custom training, containers, `AIP_MODEL_DIR` | `05_gcp/04_custom_training` |
| pipelines and a deployment gate | `06_pipelines` |

All in the MLE repo. If a question here needs more depth, follow the link rather than expecting
this section to grow.

## What was actually run

| | |
|---|---|
| `01_bigquery_ml/bqml_patterns.sql` | 📝 **never submitted** — correct, sandbox-ready |
| Vertex AI | 📝 **write-only** |

Nothing in this section executes. That is the honest state: BQML needs a project, and the modelling
content it would otherwise demonstrate is already measured in the other repository.

**Naming note:** Vertex AI was renamed **Gemini Enterprise Agent Platform** in June 2026, but the
PDE exam objectives and both source guides still say "Vertex AI", so this section does too. Writing
a name the exam does not use would be its own kind of wrong — see
[`99_reference/SERVICE_NAMES.md`](../99_reference/SERVICE_NAMES.md).
