# BigQuery ML

> **Domain 4 (15%)** · Success Guide pp. 56–58 · Ultimate §4.2
> **Runtime:** — · **Needs:** a project, to run the SQL for real

`bqml_patterns.sql` — correct, sandbox-ready, **never submitted**.

---

## 1. What it is

BigQuery ML trains and serves models **with SQL, where the data already is**. No export, no
training cluster, no serving system. `CREATE MODEL` is a query; `ML.PREDICT` is a query.

That is the entire pitch, and it is a strong one: most of the cost and most of the failure modes in
an ML pipeline come from moving data between systems, and BQML removes the moving.

## 2. Components

| component | what it is |
|---|---|
| **`CREATE MODEL`** | Trains. The model is an object in a dataset. |
| **`MODEL_TYPE`** | Which algorithm. The catalogue is deliberately narrow. |
| **`TRANSFORM`** | Preprocessing stored *inside* the model, reapplied at prediction. |
| **`DATA_SPLIT_METHOD`** | How train/eval is divided. **The default is random.** |
| **`ML.EVALUATE` / `ML.PREDICT` / `ML.FORECAST`** | Score, predict in batch, forecast. |
| **`ML.FEATURE_IMPORTANCE`** | What the model leaned on. |
| **Imported / remote models** | A model trained elsewhere, called from SQL. |

## 3. The model types PDE tests

| type | when |
|---|---|
| **`ARIMA_PLUS`** | **the most likely question** — forecasting, and `TIME_SERIES_ID_COL` fits thousands of series in one statement |
| `LINEAR_REG` / `LOGISTIC_REG` | baselines, and interpretable |
| `BOOSTED_TREE_*` | tabular classification and regression |
| `KMEANS` | segmentation — needs `STANDARDIZE_FEATURES` |
| `MATRIX_FACTORIZATION` | recommendations from historical behaviour, transactions or ratings |
| `PCA` | **dimensionality reduction** — project onto the first few principal components |
| `TENSORFLOW` / `ONNX` (imported) | a model you already trained |
| `REMOTE` | calls a Vertex endpoint from SQL |

## 4. Preparing the data

| technique | what it fixes | in BQML |
|---|---|---|
| **One-hot encoding** | algorithms need numbers, not `"Red"` | **automatic** for `STRING` features — you rarely write it yourself |
| **Standardising** | features on wildly different scales | automatic for most types; **`STANDARDIZE_FEATURES` matters for `KMEANS`** |
| **Class balancing** | 99% legitimate / 1% fraud — the model learns to always say "legitimate" | oversample the minority, undersample the majority, or `AUTO_CLASS_WEIGHTS=TRUE` |
| **`TRANSFORM`** | preprocessing that must match at serving time | stored **inside the model** and reapplied automatically by `ML.PREDICT` |

> **`TRANSFORM` is the training/serving-skew fix**, and it is the same problem Vertex's Feature
> Store solves ([`../02_vertex_ai/`](../02_vertex_ai/)). Preprocessing written as a separate query
> *will* drift from what the model was trained on.

## 5. Evaluating a model

**Always `ML.EVALUATE` before anything is deployed.** Which metric depends on what a mistake costs.

### Classification

| metric | measures | use when |
|---|---|---|
| **Precision** | of the things we flagged, how many were right | **a false positive is expensive** — spam filtering |
| **Recall** | of the real positives, how many we caught | **a false negative is expensive** — disease or fraud detection |
| **F1** | harmonic mean of the two | **imbalanced data**, where accuracy is meaningless |
| **ROC-AUC** | true-positive vs false-positive rate across all thresholds | comparing classifiers independent of threshold |

> **Accuracy is the trap on imbalanced data.** A model that always predicts "legitimate" on a 99/1
> fraud set is **99% accurate** and worthless. F1 or recall is what the question is really asking
> for.

### Regression

| metric | note |
|---|---|
| **RMSE** | back on the target's own scale, and **heavily penalises large errors** |
| **MAE** | average error magnitude, intuitive, treats all errors equally |
| **R²** | proportion of variance explained; best possible is **1.0** |

### Bias, variance, and which way a model is failing

| | cause | symptom |
|---|---|---|
| **High bias** | assumptions too simple | **underfitting** — poor on training *and* test data |
| **High variance** | too sensitive to noise | **overfitting** — excellent on training, poor on unseen |

Simplifying cuts variance and raises bias; adding complexity does the reverse. **Training accuracy
far above test accuracy is overfitting**, and it is the thing a proper evaluation split exists to
reveal — which is exactly why `AUTO_SPLIT` under 500 rows is dangerous.

## 6. Nuances — the part worth reading

**`AUTO_SPLIT` is the default and changes behaviour with row count:**

| rows | behaviour |
|---|---|
| **< 500** | **every row trains. No evaluation set exists.** |
| 500 – 50,000 | 80 / 20, random |
| > 50,000 | 10,000 rows eval, rest train, random |

> Under 500 rows, `ML.EVALUATE` scores the model on data it trained on. The result looks
> excellent, means nothing, and **nothing warns you**. A small lookup table is exactly the case
> where someone tries BQML first.

**The split is random, so it leaks the future on time-ordered data.** Use `SEQ` with a date column,
or `CUSTOM` with your own boolean. This is not a subtlety — the MLE repo measured a random split on
a time series making the error look **2× better** than it was.

**`ML.PREDICT` is batch.** It scans, scores, returns. There is no per-row latency story and no
endpoint. "A user is waiting" is a Vertex endpoint question, always.

**Leakage is a data-engineering failure and BQML cannot see it.** The test is:
*at prediction time, does this column exist yet?* Predicting trip duration with `end_time` present
gives a perfect model that cannot run. AutoML cannot detect this either — it removes the
architecture search, not the thinking.

**`TRANSFORM` is the best defence against training/serving skew in BQML**, because preprocessing
stored inside the model is reapplied automatically at prediction time. Preprocessing done in the
`SELECT` that feeds `CREATE MODEL` is *not* — and then serving silently uses different features.

**Check `ML.FEATURE_IMPORTANCE` when a model looks too good.** A single dominant feature is usually
a leak rather than a discovery.

**BQML is priced on bytes processed, like any query.** `CREATE MODEL` over `SELECT *` on a large
table is an expensive way to find out you wanted three columns.

## 7. When to use it — and when not

| situation | reach for |
|---|---|
| data in BigQuery, standard model, no ML team | **BigQuery ML** |
| forecasting many series at once | **`ARIMA_PLUS`** |
| an existing TF/ONNX model, data in BigQuery | **import**, or a **remote model** |
| custom architecture, custom loss, GPUs | **Vertex AI custom training** |
| online, low-latency serving | **Vertex endpoint** |
| deep learning on images, video, audio | **Vertex AI** — not BQML |

**The strongest signal in an exam question is where the data is.** Already in BigQuery and a
standard problem → BQML. Anything requiring a custom training loop → Vertex.

## 8. What was actually run

| | |
|---|---|
| `bqml_patterns.sql` | 📝 **never submitted** |
| Cloud resources | **none** |

The SQL is correct and runs unmodified in the free BigQuery sandbox. The `AUTO_SPLIT` thresholds in
§4 were **verified against Google's `CREATE MODEL` documentation**, not recalled — they are the
kind of specific numeric fact that is easy to misremember and consequential to get wrong.

**Sources:** [CREATE MODEL for generalized linear
models](https://cloud.google.com/bigquery/docs/reference/standard-sql/bigqueryml-syntax-create-glm) ·
[CREATE MODEL for boosted
trees](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/bigqueryml-syntax-create-boosted-tree)
