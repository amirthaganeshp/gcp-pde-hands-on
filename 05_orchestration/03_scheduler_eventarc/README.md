# Cloud Scheduler and Eventarc

> **Domain 5 — Maintaining and Automating Workloads (18%)** · Success Guide §11.2, §11.3
> 📝 **Write-only** — both are managed services with no local runtime.

---

## 1. What they are

The two ways a pipeline **starts** when nothing else is orchestrating it.

| | **Cloud Scheduler** | **Eventarc** |
|---|---|---|
| fires on | **the clock** (cron) | **something happening** |
| the question | "every night at 02:00" | "when a file lands in this bucket" |

Between them and Composer, that is the whole trigger landscape: **time**, **event**, or
**dependency graph**.

## 2. Cloud Scheduler

Fully managed, enterprise-grade cron.

| property | detail |
|---|---|
| **Targets** | HTTP(S) endpoints, **Pub/Sub topics**, App Engine |
| **Delivery** | **at-least-once**, with built-in retries and **exponential backoff** |
| **Auth** | OIDC/OAuth tokens via a service account — can invoke private Cloud Run |
| **Schedule** | standard cron, with an explicit **timezone** |

**Why not plain cron on a VM:** if the VM is down the job simply does not run, there is no
centralised logging, and no retry. Scheduler has all three — and nothing to patch.

```bash
gcloud scheduler jobs create pubsub nightly-etl \
    --schedule="0 2 * * *" --time-zone="America/New_York" \
    --topic=etl-trigger --message-body='{"job":"daily"}'
```

**The common pattern:** Scheduler → Pub/Sub → Cloud Run/Function → launches a **Dataflow
template**. That is how a batch pipeline runs nightly without an Airflow environment billing
continuously.

## 3. Eventarc

The standardised **event router**. It listens to Google Cloud sources and delivers **CloudEvents**
to a destination.

| | |
|---|---|
| **Sources** | direct events (e.g. **GCS object finalized**), **Cloud Audit Logs** (nearly any API call), Pub/Sub messages |
| **Destinations** | Cloud Run, Cloud Run functions, GKE, Workflows |
| **Transport** | Pub/Sub underneath — so ordering and retry behave accordingly |

**The IAM detail that is actually tested:** the trigger's service account needs
**`roles/eventarc.eventReceiver`**, *and* permission to invoke the destination —
`roles/run.invoker` for Cloud Run. Missing the second is the usual cause of a trigger that fires
and does nothing.

**Audit-log-based triggers are the powerful ones**: "when anyone creates a BigQuery dataset",
"when a table is deleted" — events for things that have no native event source.

## 4. Choosing a trigger

| the requirement | use |
|---|---|
| "every night at 2 am" | **Cloud Scheduler** |
| "when a file lands in the bucket" | **Eventarc** |
| "when this finishes, then that, and retry, and backfill" | **Composer** |
| "a chain of API calls, serverless" | **Workflows** (started by Scheduler or Eventarc) |
| "one recurring SQL statement" | **BigQuery scheduled query** |

> **The over-engineering to avoid:** standing up a Composer environment — which bills
> continuously — to run one nightly query. Scheduler costs effectively nothing and has retries.
> Conversely, chaining ten Scheduler jobs by guessing at durations is a fragile reimplementation
> of a DAG, and *that* is when you do want Composer.

## 5. Nuances — the part worth reading

**At-least-once means the target must be idempotent.** A retried Scheduler job runs your pipeline
twice. Same discipline as [Pub/Sub](../../01_ingestion/01_pubsub/) and
[Airflow retries](../01_composer/): `MERGE`, not `INSERT`.

**Scheduler has no dependency awareness.** It fires on the clock whether or not yesterday's run
finished. Two jobs scheduled an hour apart because "the first takes about 40 minutes" will
eventually overlap.

**Eventarc's ordering is Pub/Sub's ordering** — which is to say, not guaranteed unless you have
asked for it. Events for the same object can arrive out of order.

**Event-driven beats polling.** A Scheduler job that checks every five minutes whether a file has
arrived is both slower and more expensive than an Eventarc trigger that fires on arrival.

## 6. What was actually run

**Nothing.** Both are managed trigger services with nothing to run locally. The thing they
typically trigger — a DAG, a Dataflow template — is covered in
[`../01_composer/`](../01_composer/) and [`../../02_beam_dataflow/`](../../02_beam_dataflow/).
