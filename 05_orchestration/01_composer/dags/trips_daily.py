"""A DAG exercising the Airflow features the PDE exam actually asks about.

Cloud Composer IS managed Apache Airflow, so this DAG is the same DAG
you would deploy to a Composer environment - only the place it runs
changes. That is why this section can be taught locally.

It deliberately touches, in one graph:

    ingest -> validate -> branch ---> transform -> load
                                \
                                 --> skip_load
                                              \
                                               -> report (ALWAYS runs)

  - the DATA INTERVAL, and why it is not "now"
  - BRANCHING, and what happens to the branch not taken
  - TRIGGER RULES - how `report` runs either way
  - XCom for small values, and why not for data
  - retries and a task-level SLA

Run it without a scheduler, which is how you should develop DAGs:
    airflow dags test trips_daily 2026-06-05

Guide reference: Success Guide pp. 105-114; Ultimate Edition section 5.2.
"""

from __future__ import annotations

import pendulum
from airflow.decorators import dag, task
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule

# A row count below this sends the DAG down the "do not load" branch.
MIN_ROWS = 100


@dag(
    dag_id="trips_daily",
    # Airflow runs an interval AFTER it ends. A @daily DAG for
    # 2026-06-05 starts on 2026-06-06 - the single most common
    # confusion in Airflow, and it is deliberate: the interval must be
    # over before its data is complete.
    schedule="@daily",
    start_date=pendulum.datetime(2026, 6, 1, tz="UTC"),
    # Do not run every missed interval since start_date on first deploy.
    catchup=False,
    # One run at a time. Without this, a slow run and the next one
    # overlap and both write the same partition.
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": pendulum.duration(minutes=5),
        "retry_exponential_backoff": True,
    },
    tags=["pde", "example"],
    doc_md=__doc__,
)
def trips_daily():

    @task
    def ingest(**context) -> str:
        """Read the partition for THIS DAG RUN's data interval.

        `data_interval_start` - not `now()`, and not `datetime.today()`.
        Using a wall clock here is the bug that makes a backfill
        reprocess today's data N times instead of each historical day
        once, and it fails silently.

        CAVEAT, because this file's own output shows it: under
        `airflow dags test` the interval COLLAPSES - start and end print
        as the same instant. A scheduled run has
        end = start + schedule. So `dags test` is the right tool for
        checking task logic and the WRONG one for reasoning about
        intervals; use `airflow dags backfill` or read a real run.
        """
        start = context["data_interval_start"]
        end = context["data_interval_end"]
        partition = start.format("YYYY-MM-DD")
        print(f"  data_interval : {start} -> {end}")
        print(f"  reading partition {partition}")
        return partition

    @task
    def validate(partition: str) -> int:
        """Return a row count. Small values travel by XCom.

        XCom is for SMALL values - an id, a count, a path. It is stored
        in the metadata database, so putting a DataFrame through it
        bloats that database and eventually breaks the scheduler. Pass a
        POINTER to data, never the data.
        """
        # HARDCODED stand-ins, NOT read from data/: one quiet date forces
        # the skip branch. The numbers are not measured from the dataset.
        row_count = 4_812 if partition != "2026-06-03" else 12
        print(f"  {partition}: {row_count:,} rows")
        return row_count

    @task.branch
    def decide(row_count: int) -> str:
        """Choose ONE downstream path, by returning its task id.

        Everything downstream of the branch that is NOT returned is
        marked `skipped` - and skipping propagates, which is exactly
        why `report` below needs a trigger rule.
        """
        if row_count < MIN_ROWS:
            print(f"  {row_count} < {MIN_ROWS} - not loading")
            return "skip_load"
        print(f"  {row_count} >= {MIN_ROWS} - loading")
        return "transform"

    @task
    def transform(partition: str) -> str:
        print(f"  transforming {partition}")
        return f"gs://bucket/staged/{partition}"

    @task
    def load(staged_uri: str) -> int:
        """In a real DAG this is a MERGE, not an INSERT.

        A task can be retried, and an upstream at-least-once source can
        deliver twice, so the load must be idempotent on a business key.
        See 03_bigquery/01_bigquery/bigquery_patterns.sql section 8.
        """
        print(f"  MERGE from {staged_uri}")
        return 4_812

    skip_load = EmptyOperator(task_id="skip_load")

    @task(
        # WITHOUT this the DAG would end `skipped` on the quiet day,
        # because skipping propagates downstream by default. This rule
        # is what makes "run either way" work.
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
        sla=pendulum.duration(hours=2),
    )
    def report(**context):
        ti = context["ti"]
        rows = ti.xcom_pull(task_ids="load")
        state = "loaded" if rows else "skipped"
        print(f"  run {context['data_interval_start'].to_date_string()}: "
              f"{state}, rows={rows}")

    partition = ingest()
    rows = validate(partition)
    branch = decide(rows)

    staged = transform(partition)
    loaded = load(staged)

    branch >> [staged, skip_load]
    [loaded, skip_load] >> report()


dag = trips_daily()
