# gcloud learning — Professional Data Engineer

A **runnable** companion to the 117-page *Success Guide: GCP Professional Data Engineer*. Where the
guide says "session windows close after a gap of inactivity," this repository lets you change the
gap and watch the window count move.

> **Not exam prep.** The certification is already held. This is a reference you can execute.

---

## The thing that makes this possible

PDE is a cloud-services exam, so the obvious objection is that nothing runs without a project and a
bill. That turns out to be mostly wrong — the two heaviest technologies on the exam are open source
with local runners, and Google ships official emulators for most of the rest.

| service | runs locally? | how |
|---|---|---|
| **Dataflow** | ✅ fully | Apache Beam local runner — *same pipeline code* |
| **Managed Service for Apache Spark** | ✅ fully | local PySpark — it **is** Spark |
| **Composer** | ✅ fully | Airflow standalone — Composer **is** managed Airflow |
| Pub/Sub · Bigtable · Firestore · Spanner | ✅ | official `gcloud` emulators |
| **BigQuery** | ⚠️ partial | no official emulator — real SQL, free sandbox, local simulation |
| Dataplex · DLP · Data Fusion | ❌ | write-only, clearly labelled |

**No project, no billing, no credentials required** for anything marked ✅.

## Platform: WSL Ubuntu, not Windows

Not a preference. **Airflow does not run on Windows** — unsupported, not merely awkward. PySpark and
the emulators need a JVM, which is one `apt` command here. And `pip` reaches the internet directly
inside WSL, with none of the corporate-TLS workarounds Windows needs.

```bash
python3 -m venv ~/venvs/pde
~/venvs/pde/bin/pip install -r requirements.txt
```

Kept separate from any other venv so a Beam or Airflow dependency resolution cannot disturb it.

`requirements.txt` covers every Python import **except Airflow**, which has its own venv
(`~/venvs/airflow`) — see [`05_orchestration/01_composer/`](05_orchestration/01_composer/). What pip
cannot install is a system piece, and each script names the one it needs: **Java 17+** (Spark,
the emulators, Kafka), **`redis-server`**, the **gcloud emulators**, and an **Apache Kafka release
unpacked at `~/kafka`** — not downloaded by the script; see
[`01_ingestion/02_kafka/`](01_ingestion/02_kafka/).

## Sections

Full subtopic and service breakdown: **[SYLLABUS.md](SYLLABUS.md)**.

| | services | state |
|---|---|---|
| [`00_setup/`](00_setup/) | environment check, synthetic data generator | ✅ built |
| [`01_ingestion/`](01_ingestion/) | Pub/Sub · **Apache Kafka** | ✅ built |
| [`02_beam_dataflow/`](02_beam_dataflow/) | Dataflow (Apache Beam) — **model, streaming, batch** | ✅ built |
| [`03_bigquery/`](03_bigquery/) | **BigQuery** · **Dataform** · BigLake/Omni | ✅ built · 📝 rest |
| [`04_managed_spark/`](04_managed_spark/) | **Managed Spark** · Data Fusion · Dataprep | ✅ built · 📝 rest |
| [`05_orchestration/`](05_orchestration/) | **Composer (Airflow)** · Workflows · Scheduler/Eventarc | ✅ built · 📝 rest |
| [`06_storage_decisions/`](06_storage_decisions/) | **object · in-memory · Bigtable · Firestore** · block · file · SQL | ✅ 4 run · 📝 3 |
| [`07_migration_cdc/`](07_migration_cdc/) | **Datastream CDC** · **transfer arithmetic** · DMS | ✅ built · 📝 rest |
| [`08_sharing_and_viz/`](08_sharing_and_viz/) | **Analytics Hub / clean rooms** · BI Engine · Looker | ✅ built · 📝 rest |
| [`09_ml_integration/`](09_ml_integration/) | BigQuery ML · Vertex AI | 📝 documented (BQML SQL written, never submitted) |
| [`10_governance_security/`](10_governance_security/) | **Sensitive Data Protection** · IAM · KMS · Dataplex · VPC SC | ✅ built · 📝 rest |
| [`11_ops_cost_monitoring/`](11_ops_cost_monitoring/) | **cost crossovers** · **alerting conditions** · Logging | ✅ built · 📝 rest |
| [`12_capstone/`](12_capstone/) | **one end-to-end pipeline + four failure modes** | ✅ built |
| [`99_reference/`](99_reference/) | **findings** · decision tables · exam-domain map · CLI · glossary · renames | ✅ built |

**~45 services.** Depth follows the exam weights, not convenience — domain 2 (ingest and process)
is heaviest at 25%, which is why `01` and `02` get the most work. The 117-page guide agrees,
spending 47 pages there and mentioning `watermark` 19 times.

## Layout: one folder, one README, one set of examples per service

A **section** README covers the decision *between* services. A **service** README covers the
service itself, in six fixed parts: what it is · components · fundamental operations ·
**nuances** · when to use it and when not · what was actually run.

Coverage is driven by **both guides**, not by what happens to be runnable here — so a service
README documents the components the guides describe even when no local example can exercise them.
Where a folder has runnable scripts it also carries an **`EXAMPLES.md`** explaining what each
illustration sets up and which exam idea its measurement makes concrete.

**✅ built** means something in that folder executes. **📝 documented** means the service has no
honest local proxy — and nothing was simulated to pretend otherwise.

```
01_ingestion/
  README.md              Pub/Sub vs Kafka - the decision
  01_pubsub/
      README.md          the service
      pubsub_basics.py   runnable
  02_kafka/
      README.md
      kafka_basics.py
```

Part 4, **nuances**, is the one worth writing: defaults nobody chose, limits, and the failures that
raise nothing.

## The data

One synthetic dataset, generated from a seed, used by every section — a **bike-share trip stream**.
It was designed backwards from what the sections need:

```bash
python 00_setup/make_data.py
```

- **50,000 trips**, 14 days, 8 stations
- a real **event-time vs processing-time** gap: median lag **11.2 s**, p95 **423.5 s**
- **8.0% of events arrive minutes late**, not seconds — which is what makes watermarks and
  allowed-lateness observable rather than merely described
- a natural partition key (date) and cluster key (station) for BigQuery
- a small stations dimension to join against

Nothing is downloaded and nothing is real.

## Conventions

Inherited deliberately from the ML repo, because they are what made it worth reading:

- Every script **standalone and runnable from the repo root**, seeded, with narrated stdout.
- **Under ~2 minutes** per example; anything heavier behind `--full`.
- An explicit **"what was actually run"** table per section — executed vs write-only, never blurred.
- **Honest findings kept**, including the inconvenient ones.
- No employer data, names or project IDs anywhere.

New here: **every emulator-backed example starts and stops its own emulator**, so any one file can
be run without reading the setup guide first.

---

## Verified environment

Recorded because "it works on my machine" is the thing this repo exists to avoid:

| | |
|---|---|
| OS | Ubuntu 24.04.5 LTS under WSL2 (kernel 6.18.33) |
| Python | 3.12.3 |
| Apache Beam | 2.76.0 |
| resources | 22 cores, 15 GB RAM |
