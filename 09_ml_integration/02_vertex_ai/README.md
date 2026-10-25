# Vertex AI — the data engineer's slice

> **Domain 4 — Preparing and Using Data for Analysis (15%)** · Success Guide pp. 56–62 · Ultimate §4.2
> 📝 **Write-only** — Vertex AI is a managed platform; nothing here was executed.

---

## 1. What it is

Google's unified ML platform. **On the PDE exam you are not being asked to be an ML engineer** —
you are asked to prepare data correctly, choose between BQML and Vertex, and know where a model is
served from. That boundary is what this folder covers.

## 2. Components worth knowing

| component | what it is |
|---|---|
| **Pretrained APIs** | Ready-to-call models — **Vision** (OCR, object/face detection), **Translation**, **Natural Language** (sentiment, entities), Speech. No training. |
| **AutoML** | Upload tabular, image or text data; Vertex searches architectures and trains for you. |
| **Custom training** | Your own TensorFlow/PyTorch/scikit-learn script in a container. Full control. |
| **Vertex AI Pipelines** | ML workflow orchestration (Kubeflow-based) with lineage. |
| **Feature Store** | Shared, versioned features — and **consistency between training and serving**. |
| **Model Registry** | Versioned models and their metadata. |
| **Endpoints** | **Online, low-latency** serving. |
| **Batch prediction** | Large offline scoring jobs. |
| **Vector Search** | Nearest-neighbour search over **billions of embeddings**, in milliseconds. |
| **Vertex AI Search and Conversation** | Search engines and chatbots grounded in GCS/BigQuery/web data. |

> **Name check:** the agent-building surface has been renamed more than once (Gen App Builder →
> Search and Conversation → Agent Platform). See
> [`99_reference/SERVICE_NAMES.md`](../../99_reference/SERVICE_NAMES.md).

## 3. The decision — BQML or Vertex?

| situation | use |
|---|---|
| data already in BigQuery, standard model type | **BigQuery ML** — don't move terabytes to move them back |
| forecasting many series at once | **`ARIMA_PLUS`** in BQML |
| an existing TF/ONNX model to score in SQL | **import it**, or a **remote model** calling a Vertex endpoint |
| custom architecture, custom loss, a framework | **Vertex custom training** |
| image, video, audio, free text | **Vertex** (pretrained API or AutoML) |
| **a user is waiting, sub-second** | **Vertex endpoint** — `ML.PREDICT` is a **batch** operation |

**That last row is the one the exam tests.** `ML.PREDICT` is a query. It is excellent for scoring a
table and useless for a request-response API.

## 4. Data preparation — the actually-examinable part

### Splits

| set | for |
|---|---|
| **Training** | teaching the model |
| **Validation** | tuning hyperparameters, detecting overfitting *during* training |
| **Test** | final evaluation on data the model has never seen |

> **A random split leaks the future.** For time-series or any temporal target, split
> **chronologically** — train on earlier data, test on later. A random split lets the model learn
> from events after the ones it is predicting, and produces an accuracy figure that is simply
> false.

**Other leakage sources:** a feature computed from the label; normalising over the *whole* dataset
before splitting; the same entity appearing in both train and test.

### Embeddings and RAG

Unstructured input → an **embedding model** → float vectors capturing semantic meaning → indexed in
**Vector Search** → nearest-neighbour retrieval grounds an LLM's answer in your data. The data
engineer owns the pipeline that chunks, embeds and refreshes that index — which is an ordinary ETL
problem with an unusual output type.

## 5. Nuances — the part worth reading

**Training/serving skew is the failure mode this platform exists to prevent.** If a feature is
computed one way in the training pipeline and another way at serving time, the model degrades
silently — accuracy in evaluation, nonsense in production. **Feature Store** solves it by making
both read the same definition.

**Pretrained API before AutoML before custom training.** The cheapest correct answer wins: if the
task is OCR or sentiment, the Vision or NL API is done today and a custom model is months. Reach
for custom training only when the requirement genuinely cannot be met otherwise.

**Batch vs online is a data-engineering decision, not an ML one.** It determines the entire
serving architecture, and it is decided by whether a human is waiting.

**Vertex does not absolve you of data quality.** Profiling, null handling, class imbalance and
leakage are all upstream of anything here — see
[`../../10_governance_security/04_knowledge_catalog/`](../../10_governance_security/04_knowledge_catalog/).

## 6. What was actually run

**Nothing.** Vertex AI requires a project and billing.

The **SQL-side ML path is covered** in [`../01_bigquery_ml/`](../01_bigquery_ml/), and the
statistical rigour this section depends on — honest evaluation rather than a flattering number — is
demonstrated in [`99_reference/FINDINGS.md`](../../99_reference/FINDINGS.md).
