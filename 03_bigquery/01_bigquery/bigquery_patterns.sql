-- BigQuery patterns worth knowing, as real SQL.
--
-- NEVER SUBMITTED. Every statement here is correct and runs unmodified
-- against a project, including the free BigQuery sandbox (no card,
-- 10 GB storage, 1 TB of queries a month). Nothing in this file has been
-- executed, and no project id appears in it.
--
-- The measured cost mechanics behind sections 1-3 are in
-- partition_pruning.py.
--
-- Guide reference: Success Guide pp. 34-58; Ultimate Edition section 3.4.

-- ===================================================================
-- 1. PARTITIONING - the single biggest cost control
-- ===================================================================

-- Partition by DATE. The engine skips any partition the filter excludes.
CREATE OR REPLACE TABLE `dataset.trips`
(
  trip_id       STRING  NOT NULL,
  event_time    TIMESTAMP NOT NULL,
  trip_date     DATE      NOT NULL,
  start_station STRING,
  end_station   STRING,
  bike_type     STRING,
  duration_min  FLOAT64,
  distance_km   FLOAT64,
  member        BOOL
)
PARTITION BY trip_date
CLUSTER BY start_station, bike_type
OPTIONS (
  -- Turns "someone forgot the WHERE clause" from a bill into an error.
  -- The most effective single cost control BigQuery offers.
  require_partition_filter = TRUE,
  partition_expiration_days = 400,
  description = 'Bike share trips, partitioned daily, clustered by station'
);

-- Partitioning on a TIMESTAMP needs an explicit truncation.
CREATE OR REPLACE TABLE `dataset.trips_ts`
PARTITION BY DATE(event_time)
CLUSTER BY start_station
AS SELECT * FROM `dataset.trips_raw`;

-- Integer-range partitioning, for when the natural key is not a date.
CREATE OR REPLACE TABLE `dataset.trips_by_station_id`
PARTITION BY RANGE_BUCKET(station_id, GENERATE_ARRAY(0, 10000, 100))
AS SELECT * FROM `dataset.trips_raw`;


-- ===================================================================
-- 2. PRUNING THAT WORKS, AND PRUNING THAT SILENTLY DOES NOT
-- ===================================================================

-- GOOD: a literal predicate directly on the partition column.
SELECT start_station, COUNT(*) AS trips
FROM `dataset.trips`
WHERE trip_date BETWEEN '2026-06-01' AND '2026-06-07'
GROUP BY start_station;

-- BAD: the partition column is wrapped in a function, so the engine
-- cannot decide which partitions to open before reading them.
-- This returns the right answer and scans the WHOLE TABLE.
SELECT COUNT(*)
FROM `dataset.trips`
WHERE EXTRACT(MONTH FROM trip_date) = 6;          -- full scan

-- The same question, prunable:
SELECT COUNT(*)
FROM `dataset.trips`
WHERE trip_date >= '2026-06-01' AND trip_date < '2026-07-01';

-- ALSO BAD: comparing the partition column to a subquery. Whether this
-- prunes depends on whether the engine can resolve the subquery first -
-- do not rely on it. Resolve to a literal and parameterise instead.
SELECT COUNT(*)
FROM `dataset.trips`
WHERE trip_date = (SELECT MAX(trip_date) FROM `dataset.trips`);


-- ===================================================================
-- 3. COST CONTROL
-- ===================================================================

-- Dry run: how many bytes WOULD this scan? Costs nothing and answers
-- the question before the bill does. (bq CLI: --dry_run)
-- In the console this is the "This query will process N" estimate.

-- A hard ceiling per query - the job fails rather than overspends.
-- bq query --maximum_bytes_billed=1000000000 '...'

-- Never do this on a large table just to see what is in it:
SELECT * FROM `dataset.trips` LIMIT 10;
-- LIMIT does NOT reduce bytes scanned. The engine reads the columns
-- then discards rows. Use table preview, or TABLESAMPLE:
SELECT * FROM `dataset.trips` TABLESAMPLE SYSTEM (1 PERCENT);


-- ===================================================================
-- 4. VIEWS, AUTHORISED VIEWS, MATERIALIZED VIEWS
-- ===================================================================

-- A view is stored SQL. It costs nothing to keep and re-runs every time.
CREATE OR REPLACE VIEW `dataset.v_daily_trips` AS
SELECT trip_date, start_station, COUNT(*) AS trips
FROM `dataset.trips`
WHERE trip_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
GROUP BY trip_date, start_station;

-- A MATERIALIZED view stores its result and BigQuery keeps it fresh,
-- incrementally. Queries against the base table are transparently
-- rewritten to use it when they can be.
CREATE MATERIALIZED VIEW `dataset.mv_daily_trips`
PARTITION BY trip_date
CLUSTER BY start_station
OPTIONS (enable_refresh = TRUE, refresh_interval_minutes = 30)
AS
SELECT trip_date, start_station, COUNT(*) AS trips,
       SUM(distance_km) AS km
FROM `dataset.trips`
GROUP BY trip_date, start_station;
-- Constraints that bite: no OUTER JOIN, no UNION, no analytic functions,
-- and only a limited set of aggregates. If the view will not create,
-- the restriction is almost always one of those.

-- An AUTHORISED view shares a SLICE of a table without granting access
-- to the table itself. The consumer is granted access to the VIEW's
-- dataset only, and the view is authorised on the source dataset.
CREATE OR REPLACE VIEW `shared_dataset.v_station_totals` AS
SELECT start_station, COUNT(*) AS trips        -- no trip_id, no member
FROM `private_dataset.trips`
GROUP BY start_station;


-- ===================================================================
-- 5. NESTED AND REPEATED - denormalise instead of joining
-- ===================================================================

CREATE OR REPLACE TABLE `dataset.stations_nested` AS
SELECT
  start_station AS station,
  COUNT(*)      AS total_trips,
  ARRAY_AGG(STRUCT(trip_id, event_time, duration_min)
            ORDER BY event_time LIMIT 100) AS recent_trips
FROM `dataset.trips`
GROUP BY start_station;

-- UNNEST turns the array back into rows. This is a CROSS JOIN against
-- each row's own array, not a shuffle - which is the point: the nested
-- layout avoids the join entirely.
SELECT s.station, t.trip_id, t.duration_min
FROM `dataset.stations_nested` AS s,
     UNNEST(s.recent_trips) AS t
WHERE t.duration_min > 30;


-- ===================================================================
-- 6. INFORMATION_SCHEMA - find your own expensive queries
-- ===================================================================

-- The 10 costliest queries of the last week, by bytes billed.
SELECT
  creation_time,
  user_email,
  total_bytes_billed / POW(1024, 4)              AS tib_billed,
  TIMESTAMP_DIFF(end_time, start_time, SECOND)   AS seconds,
  total_slot_ms / 1000                           AS slot_seconds,
  SUBSTR(query, 0, 120)                          AS query_head
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND job_type = 'QUERY'
  AND state = 'DONE'
  AND error_result IS NULL
ORDER BY total_bytes_billed DESC
LIMIT 10;

-- Storage by table, and how much of it is long-term (cheaper) storage.
SELECT
  table_schema,
  table_name,
  total_logical_bytes    / POW(1024, 3) AS logical_gib,
  active_logical_bytes   / POW(1024, 3) AS active_gib,
  long_term_logical_bytes / POW(1024, 3) AS long_term_gib
FROM `region-us`.INFORMATION_SCHEMA.TABLE_STORAGE
WHERE total_logical_bytes > 0
ORDER BY total_logical_bytes DESC;

-- Which queries are queuing for slots?
SELECT job_id, reservation_id, total_slot_ms,
       TIMESTAMP_DIFF(start_time, creation_time, SECOND) AS queued_seconds
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
  AND job_type = 'QUERY'
ORDER BY queued_seconds DESC
LIMIT 20;


-- ===================================================================
-- 7. TIME TRAVEL AND RECOVERY
-- ===================================================================

-- Read the table as it was. Default window is 7 days, configurable
-- from 2 to 7.
SELECT COUNT(*)
FROM `dataset.trips`
FOR SYSTEM_TIME AS OF TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR);

-- Undo a bad DELETE by restoring into a new table.
CREATE OR REPLACE TABLE `dataset.trips_restored` AS
SELECT *
FROM `dataset.trips`
FOR SYSTEM_TIME AS OF TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 MINUTE);

-- A snapshot is a cheap, explicit point-in-time copy - it stores only
-- the delta from the base table.
CREATE SNAPSHOT TABLE `dataset.trips_snap_20260601`
CLONE `dataset.trips`
OPTIONS (expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(),
                                              INTERVAL 30 DAY));

-- A CLONE is writable and also only charges for the delta - the right
-- way to give a team a "copy" of production to experiment on.
CREATE TABLE `dataset.trips_dev` CLONE `dataset.trips`;


-- ===================================================================
-- 8. LOADING AND STREAMING
-- ===================================================================

-- An EXTERNAL table leaves the data in GCS. Good for staging and for
-- data you query rarely; slower, and no partition pruning unless the
-- files are laid out with hive partitioning.
CREATE OR REPLACE EXTERNAL TABLE `dataset.trips_external`
OPTIONS (
  format = 'PARQUET',
  uris = ['gs://your-bucket/trips/*.parquet'],
  hive_partition_uri_prefix = 'gs://your-bucket/trips'
);

-- MERGE is the idempotent upsert that makes an at-least-once pipeline
-- safe - see 01_ingestion/01_pubsub. Keyed on a BUSINESS id.
MERGE `dataset.trips` AS target
USING `dataset.trips_staging` AS source
ON target.trip_id = source.trip_id
WHEN MATCHED THEN UPDATE SET
  duration_min = source.duration_min,
  distance_km  = source.distance_km
WHEN NOT MATCHED THEN INSERT ROW;
