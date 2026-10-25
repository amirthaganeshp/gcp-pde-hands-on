# Glossary

Terms that recur across the repository, each pointing at where it is **demonstrated** rather than
merely defined.

---

## Streaming and time

**Event time vs processing time** — when it happened vs when it arrived. Measured: 273 of 50,000
trips fall in a different hour depending which clock you use. → `02_beam_dataflow`

**Watermark** — the runner's estimate that no more data will arrive for a window. → `02_beam_dataflow`

**Allowed lateness** — how long a window's state is kept after it should have closed. At 0, late
data is dropped **silently**. → `02_beam_dataflow`

**Tumbling / sliding / session windows** — partition time, overlap time, or let the *data* decide
the boundary. Sessions went 7,968 → 151 from the gap setting alone. → `02_beam_dataflow`

**Accumulating vs discarding** — whether a later pane is the whole corrected answer or only the
delta. Choosing wrong double-counts or under-counts, and both look plausible. → `02_beam_dataflow`

**At-least-once** — delivery may repeat. Demonstrated: a message redelivered after its ack deadline
expired, with nothing having failed. → `01_ingestion/01_pubsub`

**Ordering key** — orders messages sharing a key, at the cost of parallelism. → `01_ingestion/01_pubsub`

**Offset** — a Kafka consumer's own position in a partition. Rewinding it is replay. → `01_ingestion/02_kafka`

**Dead-letter topic** — where a message goes after N failed deliveries. Needs its **own
subscription** or the messages are discarded. → `01_ingestion/01_pubsub`

## Processing

**Narrow vs wide transformation** — needs only the local partition, vs needs rows from everywhere.
Wide causes the **shuffle**, which is where the cost is. → `04_managed_spark`

**Shuffle** — redistributing data by key across workers. → `04_managed_spark`

**Combiner lifting** — pre-aggregating before the shuffle. `CombinePerKey` does; `GroupByKey`
cannot. → `02_beam_dataflow`

**Side input / broadcast join** — copying a small dataset to every worker so the join needs no
shuffle. Same idea in Beam and Spark, same hard limit: it must be small. → `02_beam_dataflow`, `04_managed_spark`

**Skew** — uneven key distribution. Measured at **34.5×** imbalance from one hot key. → `04_managed_spark`

**Salting** — splitting a hot key into sub-keys to spread it. Took 34.5× to 10.8× — it helps, it
does not solve. → `04_managed_spark`

**Lazy evaluation** — transformations build a plan; only an **action** runs it. → `04_managed_spark`

**AQE** (Adaptive Query Execution) — re-plans mid-job using real statistics. Coalesces the 200
default partitions *after* the shuffle. → `04_managed_spark`

## Storage and query

**Partitioning** — physical division, usually by date. **Max 4,000 partitions.** Pruning measured
at 13.3×. → `03_bigquery`

**Clustering** — a *sort order* within partitions, so blocks can be ruled out by min/max. Measured
**6.2× vs 1.0×**. → `03_bigquery`

**Block / row group pruning** — skipping storage whose min/max cannot match. The mechanism behind
clustering. → `03_bigquery`

**Column projection** — reading only named columns. `SELECT *` measured at **11.8×** the bytes.
→ `03_bigquery`

**Materialized view** — a stored, incrementally-refreshed result; queries get rewritten to use it.
No outer joins, no analytics functions. → `03_bigquery`

**Authorised view** — shares a *slice* without granting the source table. → `08_sharing_and_viz`

**Row key** — Bigtable's only index. Sorted, and **immutable once the table has data**. → `06_storage_decisions/06_nosql/01_bigtable`

**Tablet** — a contiguous range of Bigtable's sorted key space, served by one node. → `06_storage_decisions`

**Field promotion** — moving a distinguishing field to the front of a row key to spread writes.
Reached 7.9 of 8 tablets against salting's 8.0, without destroying prefix scans. → `06_storage_decisions`

**Composite index** — Firestore's requirement for multi-field queries. **The emulator creates them
on demand; production does not.** → `06_storage_decisions/06_nosql/02_firestore`

**Long-term storage** — 50% off after 90 days **untouched**. Reading does not reset the clock;
*writing* does. → `11_ops_cost_monitoring`

**Logical vs physical billing** — uncompressed vs compressed bytes. Crossover at **2.0×**
compression. → `11_ops_cost_monitoring`

## Migration and CDC

**CDC** (change data capture) — a stream of inserts, updates and deletes rather than rows. → `07_migration_cdc`

**LSN / SCN / binlog position** — the source's monotonic sequence number. **Order by this, not by
arrival time.** → `07_migration_cdc`

**Tombstone** — a delete event. A merge that ignores them resurrects deleted rows. → `07_migration_cdc`

**Homogeneous vs heterogeneous migration** — same engine vs engine change. The second is mostly
schema conversion. → `07_migration_cdc`

**MERGE** — the idempotent upsert that makes an at-least-once pipeline safe. Keyed on a **business**
id. → `03_bigquery`, `07_migration_cdc`

## Governance

**Pseudonymisation** — a keyed, deterministic replacement. **Preserves uniqueness at 100%**, so it
is not anonymisation. → `10_governance_security`

**Generalisation / bucketing** — replacing a value with a range. The only transform that actually
reduces re-identification risk, by discarding information. → `10_governance_security`

**k-anonymity / aggregation threshold** — the minimum group size a result may have. At k=5, 59.7%
of trips survive; at k=50, none do. → `08_sharing_and_viz`

**Differencing attack** — two permitted queries whose *difference* isolates a small group.
Thresholds protect a query, not a questioner. → `08_sharing_and_viz`

**CMEK / CSEK / GMEK** — customer-managed, customer-supplied, or Google-managed keys. CMEK's trap
is the **service agent** needing `cryptoKeyEncrypterDecrypter` on the key. → `10_governance_security`

**Policy tag** — column-level access control via a taxonomy. → `10_governance_security`

## Operations

**Slot** — a unit of BigQuery compute. Capacity pricing reserves them; on-demand gets them
implicitly. → `11_ops_cost_monitoring`

**Reservation** — committed slots. Bills **time reserved**, not work done. → `11_ops_cost_monitoring`

**Trigger rule** — when an Airflow task runs given its upstreams' states. `NONE_FAILED_MIN_ONE_SUCCESS`
is the branch-join rule. → `05_orchestration`

**Data interval** — the window of *data* a DAG run covers. **Not "now"** — and `airflow dags test`
collapses it. → `05_orchestration`

**Deferrable operator** — a sensor that frees its worker slot while waiting. → `05_orchestration`

**Metric types** — gauge, delta, cumulative, distribution. **Alert on a distribution percentile,
never a mean.** → `11_ops_cost_monitoring`

**Duration window** — requiring N consecutive breaches before alerting. Removes flapping; a window
longer than your incidents cannot see them. → `11_ops_cost_monitoring`
