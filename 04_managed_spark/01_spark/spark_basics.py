"""Spark: lazy evaluation, the shuffle, skew, and broadcast joins.

Managed Service for Apache Spark - the product formerly called Dataproc,
now merged with Serverless for Apache Spark - runs Apache Spark. So the
code here is the code you would submit, and a local SparkSession
executes it for free. Only the cluster changes.

  1. Transformations vs ACTIONS - nothing happens until you ask
  2. Narrow vs WIDE - where the shuffle comes from
  3. spark.sql.shuffle.partitions - the default nobody chose
  4. SKEW - one hot key, measured, then salted
  5. BROADCAST joins - Spark's side input
  6. Caching - when it pays and when it wastes memory

EXECUTED IN FULL on a local SparkSession. No cluster, no project.

Run:
    python 00_setup/make_data.py          # once
    python 04_managed_spark/01_spark/spark_basics.py

Guide reference: Success Guide pp. 93-98; Ultimate Edition section 2.4.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

# Spark is a JVM program; PySpark drives it over a socket. Keep its
# logging out of the way of the narration.
os.environ.setdefault("PYSPARK_PYTHON", os.sys.executable)

from pyspark.sql import SparkSession, functions as F  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
TRIPS = REPO / "data" / "trips.csv"
STATIONS = REPO / "data" / "stations.csv"


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


# ============================================ 1. lazy evaluation
def lazy_evaluation(trips) -> dict:
    banner("1. Transformations vs ACTIONS")

    t0 = time.perf_counter()
    chained = (trips
               .filter(F.col("duration_min") > 10)
               .withColumn("km_per_min",
                           F.col("distance_km") / F.col("duration_min"))
               .select("trip_id", "start_station", "km_per_min"))
    build_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    n = chained.count()                       # <- the ACTION
    action_s = time.perf_counter() - t0

    print(f"  building 3 chained transformations : {build_s * 1000:>8.1f} ms")
    print(f"  calling .count() on the result     : {action_s * 1000:>8.1f} ms")
    print(f"  ratio                              : "
          f"{action_s / max(build_s, 1e-9):>8.0f}x")
    print(f"  rows returned                      : {n:>8,}")

    print("\n  **Transformations are lazy: they build a plan, they do not")
    print(f"  touch data.** Chaining three took {build_s * 1000:.0f} ms -")
    print("  schema resolution and Python overhead, not data. `count()` is")
    print("  an ACTION, and that is when Spark compiled the plan, read the")
    print("  file and did the work.")

    print("\n  Why it matters: Spark can see the WHOLE chain before running")
    print("  it, so it fuses the three steps into one pass and pushes the")
    print("  filter down to the read. Writing the same logic as three")
    print("  separate materialised steps would defeat that.")

    print("\n  The practical trap is the opposite one - calling an action")
    print("  inside a loop. Each `count()` or `collect()` re-runs the whole")
    print("  lineage from source unless you cache (section 6).")
    return {"build_ms": build_s * 1000, "action_ms": action_s * 1000, "rows": n}


# ============================================ 2-3. shuffle
def the_shuffle(spark, trips) -> dict:
    banner("2-3. Narrow vs WIDE, and the 200 nobody chose")

    base_parts = trips.rdd.getNumPartitions()

    narrow = trips.withColumn("is_long", F.col("duration_min") > 20)
    narrow_parts = narrow.rdd.getNumPartitions()

    wide = trips.groupBy("start_station").agg(F.count("*").alias("trips"))
    wide_parts = wide.rdd.getNumPartitions()

    print(f"  {'stage':<34} {'partitions':>11}")
    print("  " + "-" * 48)
    print(f"  {'source (as read)':<34} {base_parts:>11}")
    print(f"  {'after withColumn  (NARROW)':<34} {narrow_parts:>11}")
    print(f"  {'after groupBy     (WIDE)':<34} {wide_parts:>11}")

    conf_default = spark.conf.get("spark.sql.shuffle.partitions")
    print(f"\n  spark.sql.shuffle.partitions = {conf_default}")

    print("\n  **A NARROW transformation needs only the rows already in the")
    print("  partition** - map, filter, withColumn. No data moves, and the")
    print("  partition count is unchanged.")
    print("\n  **A WIDE transformation needs rows from everywhere** - groupBy,")
    print("  join, distinct, orderBy. Spark must SHUFFLE: write every")
    print("  partition to disk, redistribute by key, read it back. That is")
    print("  the expensive operation in every Spark job.")

    n_groups = wide.count()
    print(f"\n  ** THE DEFAULT NOBODY CHOSE ** the result has {n_groups} "
          f"groups")
    print(f"  spread over {wide_parts} partitions, because")
    print(f"  spark.sql.shuffle.partitions defaults to {conf_default}")
    print(f"  regardless of data size. That is "
          f"{max(0, wide_parts - n_groups)} empty partitions, each with")
    print("  a task scheduled for it.")
    print("\n  On a small job that is pure overhead; on a huge one, 200 is")
    print("  far too few and each task spills. It is the single most")
    print("  commonly tuned Spark setting, and Adaptive Query Execution")
    print("  (on by default in Spark 3+) coalesces it after the fact rather")
    print("  than removing the need to think about it.")
    return {"base": base_parts, "narrow": narrow_parts, "wide": wide_parts,
            "groups": n_groups, "conf": conf_default}


# ============================================ 4. skew
def skew_and_salting(spark, trips) -> dict:
    banner("4. SKEW - one hot key, measured, then salted")

    # Make one station dominant, which is what a real hot key looks like.
    hot = (trips
           .withColumn("station",
                       F.when(F.rand(seed=42) < 0.80, F.lit("ST01"))
                        .otherwise(F.col("start_station"))))

    def partition_sizes(df, label: str):
        sizes = (df.withColumn("pid", F.spark_partition_id())
                   .groupBy("pid").count()
                   .orderBy(F.desc("count"))
                   .collect())
        counts = [r["count"] for r in sizes]
        return counts

    grouped = hot.repartition(8, "station")
    before = partition_sizes(grouped, "skewed")

    # SALTING: split the hot key into N synthetic sub-keys so it spreads,
    # aggregate twice - once per salted key, then roll the salt up.
    salted = (hot
              .withColumn("salt", (F.rand(seed=7) * 8).cast("int"))
              .withColumn("salted_key",
                          F.concat_ws("#", F.col("station"), F.col("salt"))))
    grouped_salted = salted.repartition(8, "salted_key")
    after = partition_sizes(grouped_salted, "salted")

    print(f"  rows per partition, 8 partitions, one dominant key:\n")
    print(f"  {'':<10} {'largest':>9} {'smallest':>9} {'ratio':>8}   distribution")
    print("  " + "-" * 68)
    for label, c in (("skewed", before), ("salted", after)):
        ratio = c[0] / max(c[-1], 1)
        print(f"  {label:<10} {c[0]:>9,} {c[-1]:>9,} {ratio:>7.1f}x   {c}")

    print("\n  **Spark partitions by hash of the key, so one hot key is one")
    print("  partition, and one partition is ONE TASK on ONE core.** The")
    print("  job then runs at the speed of that single straggler no matter")
    print("  how many workers are added - the classic 'my cluster is idle")
    print("  but the job is slow'.")

    print("\n  SALTING splits the hot key into sub-keys so the work spreads,")
    print("  at the cost of a second aggregation to roll the salt back up.")
    print("  Same shape of problem as a Kafka hot partition or a Bigtable")
    print("  hot row key - and the same shape of fix.")

    print("\n  Spark 3's Adaptive Query Execution can split skewed partitions")
    print("  automatically for JOINS (spark.sql.adaptive.skewJoin.enabled).")
    print("  It does not solve a skewed groupBy, which is why salting is")
    print("  still worth knowing.")
    return {"skewed_ratio": before[0] / max(before[-1], 1),
            "salted_ratio": after[0] / max(after[-1], 1)}


# ============================================ 5. broadcast
def broadcast_join(spark, trips, stations) -> dict:
    banner("5. BROADCAST joins - Spark's side input")

    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", -1)   # off
    shuffled = trips.join(stations,
                          trips.start_station == stations.station_id)
    shuffle_plan = shuffled._jdf.queryExecution().executedPlan().toString()

    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", 10 * 1024 * 1024)
    broadcast = trips.join(F.broadcast(stations),
                           trips.start_station == stations.station_id)
    bcast_plan = broadcast._jdf.queryExecution().executedPlan().toString()

    def shuffles(plan: str) -> bool:
        """Is there a real SHUFFLE, as opposed to a BroadcastExchange?

        A naive `'Exchange' in plan` is WRONG and said so in an earlier
        version of this file: a broadcast plan contains
        `BroadcastExchange`, which matches that substring. The shuffle
        is specifically a hash/range repartition.
        """
        return ("hashpartitioning" in plan.lower()
                or "rangepartitioning" in plan.lower())

    def broadcasts(plan: str) -> bool:
        return "broadcasthashjoin" in plan.lower()

    print(f"  {'join strategy':<22} {'real shuffle?':>15} "
          f"{'BroadcastHashJoin?':>20}")
    print("  " + "-" * 60)
    print(f"  {'autoBroadcast OFF':<22} "
          f"{str(shuffles(shuffle_plan)):>15} "
          f"{str(broadcasts(shuffle_plan)):>20}")
    print(f"  {'F.broadcast(stations)':<22} "
          f"{str(shuffles(bcast_plan)):>15} "
          f"{str(broadcasts(bcast_plan)):>20}")

    print("\n  Note the test is for `hashpartitioning`, not for the word")
    print("  'Exchange' - a broadcast plan contains a BroadcastExchange, so")
    print("  the obvious substring check reports a shuffle that is not one.")

    print(f"\n  stations is {stations.count()} rows - tiny. Broadcasting it")
    print("  sends a copy to every executor, so the join happens in memory")
    print("  with **no shuffle of the large side at all**.")

    print("\n  This is exactly Beam's side input (02_beam_dataflow section 4),")
    print("  and it has exactly the same limit: the broadcast side must be")
    print("  SMALL. Broadcasting something large is an out-of-memory error")
    print("  on every executor at once, not a slow join.")

    print("\n  Spark auto-broadcasts under spark.sql.autoBroadcastJoinThreshold")
    print("  (10 MB by default). It relies on size ESTIMATES, so it misses")
    print("  when statistics are stale - which is when you hint explicitly.")
    return {"shuffle_has_shuffle": shuffles(shuffle_plan),
            "bcast_has_shuffle": shuffles(bcast_plan),
            "bcast_has_broadcast": broadcasts(bcast_plan)}


# ============================================ 6. caching
def caching(trips) -> dict:
    banner("6. Caching - when it pays")

    base = trips.filter(F.col("duration_min") > 5).select(
        "start_station", "distance_km", "bike_type")

    t0 = time.perf_counter(); base.count(); first = time.perf_counter() - t0
    t0 = time.perf_counter(); base.count(); second = time.perf_counter() - t0

    base.cache(); base.count()                      # materialise
    t0 = time.perf_counter(); base.count(); cached = time.perf_counter() - t0
    base.unpersist()

    print(f"  {'run':<28} {'seconds':>9}")
    print("  " + "-" * 40)
    print(f"  {'1st count (cold)':<28} {first:>9.3f}")
    print(f"  {'2nd count (no cache)':<28} {second:>9.3f}")
    print(f"  {'3rd count (cached)':<28} {cached:>9.3f}")

    print("\n  Without a cache, the second count RE-READ THE SOURCE and")
    print("  re-applied every transformation - Spark keeps the lineage, not")
    print("  the result. Caching stores the materialised rows instead.")
    print("\n  Cache when a DataFrame is used MORE THAN ONCE and recomputing")
    print("  it is expensive. Do not cache by default: cached data occupies")
    print("  executor memory that the shuffle also needs, and a cache that")
    print("  is read once has only cost you.")
    print("\n  At this scale the numbers are close because the dataset is")
    print("  small and the OS has it in page cache - read the mechanism,")
    print("  not the milliseconds.")
    return {"first": first, "second": second, "cached": cached}


def main() -> None:
    if not TRIPS.exists():
        raise SystemExit(f"  {TRIPS} not found - run 00_setup/make_data.py first.")

    print("=" * 72)
    print("  APACHE SPARK - what Managed Spark runs".center(72))
    print("=" * 72)

    spark = (SparkSession.builder
             .appName("pde-spark-basics")
             .master("local[4]")
             .config("spark.ui.enabled", "false")
             .config("spark.sql.adaptive.enabled", "false")  # see section 3
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")

    print(f"\n  Spark {spark.version}, master=local[4], AQE off so the")
    print("  shuffle-partition default in section 3 is visible.")

    trips = (spark.read.option("header", True).option("inferSchema", True)
             .csv(str(TRIPS)))
    stations = (spark.read.option("header", True).option("inferSchema", True)
                .csv(str(STATIONS)))

    a = lazy_evaluation(trips)
    b = the_shuffle(spark, trips)
    c = skew_and_salting(spark, trips)
    d = broadcast_join(spark, trips, stations)
    e = caching(trips)

    banner("Summary - all measured on a local SparkSession")
    print(f"  - transformations built in {a['build_ms']:.1f} ms; the action "
          f"took {a['action_ms']:.0f} ms")
    print(f"  - a WIDE transformation moved {b['base']} partitions to "
          f"{b['wide']} - the shuffle")
    print(f"  - {b['wide']} partitions for {b['groups']} groups, because "
          f"spark.sql.shuffle.partitions defaults to {b['conf']}")
    print(f"  - one hot key gave a {c['skewed_ratio']:.1f}x partition "
          f"imbalance; salting brought it to {c['salted_ratio']:.1f}x")
    print(f"  - shuffle join had a real shuffle: {d['shuffle_has_shuffle']}; "
          f"broadcast join did not: {d['bcast_has_shuffle']}")

    print("\n  Spark's cost is almost entirely the SHUFFLE. Narrow is free,")
    print("  wide is not, and skew turns a wide step into a single-core job")
    print("  however large the cluster.")

    spark.stop()


if __name__ == "__main__":
    main()
