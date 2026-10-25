# CLI reference

The `gcloud` / `bq` / `gsutil` commands worth knowing, from §6 of the *Ultimate* guide. Lookup
material — not something to run.

> **Check which project you are pointed at before any of this.** `gcloud` has an ambient default,
> and on a work machine it is very often a real production project.
>
> ```bash
> gcloud config configurations create personal
> gcloud config configurations activate personal
> gcloud config configurations list     # confirm ACTIVE, every session
> ```

---

## Orientation

```bash
gcloud config list                       # what am I pointed at?
gcloud projects list
gcloud services list --enabled           # which APIs are on
gcloud services enable dataflow.googleapis.com
gcloud auth list                         # which identity
gcloud auth application-default login    # for client libraries, not the CLI
```

## BigQuery

```bash
# ALWAYS dry-run an unfamiliar query first - it is free and tells you the bytes
bq query --use_legacy_sql=false --dry_run 'SELECT ...'

# a hard ceiling: the job FAILS rather than overspending
bq query --maximum_bytes_billed=1000000000 --use_legacy_sql=false 'SELECT ...'

bq ls --datasets
bq show --schema --format=prettyjson dataset.table
bq mk --table --time_partitioning_field=trip_date \
      --clustering_fields=start_station dataset.trips schema.json
bq load --source_format=PARQUET dataset.trips 'gs://bucket/*.parquet'
bq extract dataset.trips 'gs://bucket/out-*.parquet'
bq update --require_partition_filter=true dataset.trips
```

> **Quoting on Windows PowerShell:** backticks in GoogleSQL are eaten by PowerShell unless the
> query is a **single-quoted** string. Do not pipe a `.sql` file written by an editor into `bq` —
> a BOM produces `Illegal input character "\357"`.

## Cloud Storage

```bash
gcloud storage ls gs://bucket/**                     # the modern CLI
gcloud storage cp -r ./local gs://bucket/path
gcloud storage rsync -r ./local gs://bucket/path

gcloud storage buckets create gs://bucket \
    --location=us-central1 --default-storage-class=STANDARD \
    --uniform-bucket-level-access

gcloud storage buckets update gs://bucket --lifecycle-file=lifecycle.json
gcloud storage objects update gs://bucket/obj --storage-class=NEARLINE
```

`gsutil` still works and is what older material shows; `gcloud storage` is the current one and is
faster for large transfers.

## Pub/Sub

```bash
gcloud pubsub topics create trips
gcloud pubsub subscriptions create trips-sub --topic=trips \
    --ack-deadline=30 \
    --dead-letter-topic=trips-dlq --max-delivery-attempts=5

gcloud pubsub topics publish trips --message='{"trip_id":"T1"}'
gcloud pubsub subscriptions pull trips-sub --auto-ack --limit=10
gcloud pubsub subscriptions seek trips-sub --time=2026-06-01T00:00:00Z
```

## Dataflow

```bash
gcloud dataflow jobs list --status=active
gcloud dataflow jobs describe JOB_ID
gcloud dataflow jobs cancel JOB_ID          # discards in-flight data
gcloud dataflow jobs drain JOB_ID           # finishes in-flight first

gcloud dataflow flex-template run "job-$(date +%Y%m%d-%H%M%S)" \
    --template-file-gcs-location=gs://bucket/template.json \
    --region=us-central1 --parameters input=gs://bucket/in
```

**Drain, not cancel**, for a streaming job you want to stop cleanly — cancel discards what is in
flight.

## Managed Service for Apache Spark (formerly Dataproc)

The CLI kept the old name:

```bash
gcloud dataproc clusters create my-cluster --region=us-central1 \
    --num-workers=2 --worker-machine-type=n2-standard-4 \
    --secondary-worker-type=spot --num-secondary-workers=4

gcloud dataproc jobs submit pyspark gs://bucket/job.py \
    --cluster=my-cluster --region=us-central1

# serverless - no cluster to size or delete
gcloud dataproc batches submit pyspark gs://bucket/job.py --region=us-central1

gcloud dataproc clusters delete my-cluster --region=us-central1
```

## Composer

```bash
gcloud composer environments create my-env --location=us-central1 \
    --image-version=composer-3-airflow-2

# deploying a DAG is a file copy
gcloud composer environments storage dags import \
    --environment=my-env --location=us-central1 --source=dag.py

gcloud composer environments run my-env --location=us-central1 \
    dags list
```

## Datastream and DMS

```bash
gcloud datastream streams list --location=us-central1
gcloud datastream streams update STREAM --location=us-central1 --state=RUNNING

gcloud database-migration migration-jobs list --region=us-central1
gcloud database-migration migration-jobs promote JOB --region=us-central1
```

**`promote` is the cutover.** It ends replication and makes the destination authoritative.

## IAM

```bash
gcloud projects get-iam-policy PROJECT --format=json

gcloud projects add-iam-policy-binding PROJECT \
    --member='serviceAccount:sa@PROJECT.iam.gserviceaccount.com' \
    --role='roles/bigquery.dataViewer'

gcloud iam service-accounts create pipeline-sa
# attach it rather than downloading a key
gcloud dataflow jobs run JOB --service-account-email=sa@PROJECT.iam...
```

> **Do not create service-account keys.** A key file does not expire, cannot be rotated by the
> platform, and ends up in a repository. Attach the account, or use impersonation:
> `--impersonate-service-account=`.

## Emulators — what this repo runs on

```bash
gcloud beta emulators pubsub start --host-port=localhost:8681
gcloud beta emulators bigtable start --host-port=localhost:8086
gcloud beta emulators firestore start --host-port=localhost:8087
```

Each needs its `*_EMULATOR_HOST` environment variable set for the client to find it, and each
needs **Java**.

```bash
export PUBSUB_EMULATOR_HOST=localhost:8681
export BIGTABLE_EMULATOR_HOST=localhost:8086
export FIRESTORE_EMULATOR_HOST=localhost:8087
```

> **In WSL, `which gcloud` may return a *Windows* install under `/mnt/c`**, which cannot run the
> emulators and fails with a traceback from the Windows SDK. Prefer `/usr/bin/gcloud` explicitly.

## Monitoring and logging

```bash
gcloud logging read 'severity>=ERROR' --limit=20 --freshness=1h
gcloud logging read 'resource.type="bigquery_project"' --format=json

gcloud logging sinks create my-sink \
    bigquery.googleapis.com/projects/PROJECT/datasets/logs \
    --log-filter='resource.type="dataflow_step"'

gcloud monitoring policies list
```

## The ones worth memorising

| command | why |
|---|---|
| `bq query --dry_run` | free, and answers "how much will this cost" before it costs it |
| `--maximum_bytes_billed` | the only per-query hard stop |
| `gcloud dataflow jobs drain` | the safe way to stop a streaming job |
| `gcloud config configurations activate` | the difference between a test and an incident |
| `--impersonate-service-account` | the alternative to a key file |
