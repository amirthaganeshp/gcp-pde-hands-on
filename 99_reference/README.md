# Reference

Six documents that pull the repository together. Nothing here is new — it indexes and cross-links
what the twelve sections already demonstrated.

| file | what it is |
|---|---|
| [FINDINGS.md](FINDINGS.md) | **every measured number in one place** — cross-service patterns first |
| [DECISIONS.md](DECISIONS.md) | every "which service?" table, plus the computed crossovers |
| [EXAM_DOMAIN_MAP.md](EXAM_DOMAIN_MAP.md) | exam domain ↔ repo section ↔ guide pages, both directions |
| [CLI_REFERENCE.md](CLI_REFERENCE.md) | the `gcloud` / `bq` commands worth knowing |
| [GLOSSARY.md](GLOSSARY.md) | terms, each pointing at where it is *demonstrated* |
| [SERVICE_NAMES.md](SERVICE_NAMES.md) | the rename ledger — what things are called *now* |

---

## If you only read one page

**[FINDINGS.md](FINDINGS.md)**, and specifically its first two sections.

**§1 — one failure mode, five products.** A hot key appears in Kafka, Spark, Bigtable, Pub/Sub and
Beam, wearing a different name each time. Recognising it by *shape* — a cluster idle while the job
is slow — is worth more than five separate fixes, because the fix is always the same.

**§2 — failures that raise nothing.** Late data dropped at `allowed_lateness = 0`. A cache evicting
4,517 of 5,000 keys with every write returning OK. A naive CDC merge producing 464 rows against a
truth of 461 — close enough to pass a row-count check. Partition pruning silently not happening.
These are the expensive ones precisely because nothing errors.

## The crossovers

Four decisions that look like judgement and are arithmetic:

| decision | crossover |
|---|---|
| online transfer vs Transfer Appliance | **106 TB** at 1 Gbps |
| BigQuery on-demand vs capacity | **702 TiB** scanned/month |
| logical vs physical storage billing | **2.0×** compression |
| Standard vs Nearline storage class | **1.6 reads**/month |

## What was measured and what was not

Stated per section, and it matters:

| | |
|---|---|
| **Fully runnable** | `01_ingestion`, `02_beam_dataflow`, `04_managed_spark`, `05_orchestration`, `12_capstone` — real Kafka, Spark, Airflow, and the Pub/Sub emulator |
| **Emulator-backed** | Bigtable and Firestore, with the emulators' **leniency documented as a finding** |
| **Labelled simulation** | BigQuery cost mechanics measure **Parquet** — columnar with block min/max, so the mechanism transfers and the numbers do not |
| **Computed** | transfer times, cost crossovers, k-anonymity, de-identification, alerting precision |
| **Write-only** | IAM, KMS, VPC-SC, Analytics Hub, Looker, Vertex, Dataform, block and file storage |

What this repository does **not** do is present a Parquet or DuckDB query as a BigQuery query.

## Honest negatives

Kept rather than tuned away — [FINDINGS §7](FINDINGS.md):

- **late-pane firing did not reproduce** on any local Beam runner, checked across three
- the **Firestore emulator accepted queries production would reject**
- **salting did not solve skew** — 34.5× to 10.8×, not to 1×
- a **duration window longer than your incidents cannot see them**

## And where the narration was wrong

[FINDINGS §8](FINDINGS.md) lists seven cases where a script's own output contradicted the sentence
written next to it — a hardcoded summary claiming "all active" where the run printed `0`, a
"microseconds" that measured 118.8 ms, a substring check that matched `BroadcastExchange`.

Every one was caught by reading the output against the narration rather than by review. That habit
is the most transferable thing in the repository.

---

## Running everything

```bash
python 00_setup/make_data.py

# fully local, no emulator
python 02_beam_dataflow/01_the_beam_model.py
python 02_beam_dataflow/02_windows_and_watermarks.py
python 02_beam_dataflow/03_batch_processing.py
python 03_bigquery/01_bigquery/partition_pruning.py
python 03_bigquery/02_dataform/compile_check.py      # needs node + npx
python 04_managed_spark/01_spark/spark_basics.py
python 06_storage_decisions/01_object/storage_class_cost.py
python 07_migration_cdc/01_datastream/cdc_patterns.py
python 07_migration_cdc/02_transfer/transfer_decision.py
python 08_sharing_and_viz/01_sharing/sharing_privacy.py
python 10_governance_security/01_sensitive_data/deidentification.py
python 11_ops_cost_monitoring/01_cost/bigquery_economics.py
python 11_ops_cost_monitoring/02_monitoring/alerting_thresholds.py

# needs an emulator or a local server (each script starts its own)
python 01_ingestion/01_pubsub/pubsub_basics.py
python 01_ingestion/02_kafka/kafka_basics.py
python 06_storage_decisions/04_in_memory/memorystore_caching.py
python 06_storage_decisions/06_nosql/01_bigtable/row_key_design.py
python 06_storage_decisions/06_nosql/02_firestore/firestore_queries.py
python 12_capstone/pipeline_end_to_end.py

# its own venv - see 05_orchestration/01_composer/README.md
~/venvs/airflow/bin/airflow dags test trips_daily 2026-06-05
```

**Measured end to end: 170–185 seconds** across four runs (21 items, all exit 0 every time) on this laptop, **with no project,
no credentials and no billing.** A first run is longer, because npx fetches the Dataform CLI on first
use. Kafka is **not** downloaded by anything here: it must already be unpacked at `~/kafka`, and
`kafka_basics.py` exits with the fetch commands if it is not — see
[`01_ingestion/02_kafka/`](../01_ingestion/02_kafka/).

---

## Per-service documentation

Every service folder carries a README in a fixed shape — *what it is · components · fundamental
operations · **nuances** · when to use it and when not · what was actually run* — written to cover
the components both guides describe, not only the parts this repo can execute. **All 19 folders with
runnable scripts carry an `EXAMPLES.md`** explaining what each illustration sets up, what it
measured, and which exam idea that makes concrete — including, where it applies, the bug the
script caught and what it cannot show.

**📝 documented** means the service has no honest local proxy and nothing was simulated for it.
