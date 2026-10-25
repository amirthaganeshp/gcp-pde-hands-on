"""Kafka: the model, and where it genuinely differs from Pub/Sub.

Kafka is on the PDE exam mostly as the thing customers ARRIVE with, so
the questions are about comparison and migration rather than operating a
cluster. This file runs a real single-node broker in KRaft mode and uses
the real confluent-kafka client, so the differences are demonstrated
rather than described.

  1. The one distinction everything else follows from
  2. Topics and PARTITIONS - the unit Pub/Sub does not have
  3. Producing, and how a key decides the partition
  4. Consumer groups - the thing that makes Kafka scale, and its ceiling
  5. OFFSETS and replay - rewind and read it all again
  6. Ordering: guaranteed per partition, nowhere else
  7. Kafka vs Pub/Sub - the decision

EXECUTED IN FULL against a local broker this file starts and stops
itself. If Kafka is not installed it says how, and exits cleanly.

Run:
    python 01_ingestion/02_kafka/kafka_basics.py

Guide reference: Success Guide pp. 68-72 (Pub/Sub comparison);
Ultimate Edition section 2.2.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

BROKER = "localhost:9092"
KAFKA_HOME = Path.home() / "kafka"
TOPIC = "trips"
N_PARTITIONS = 3


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


# ============================================ broker lifecycle
def port_open(port: int) -> bool:
    with contextlib.closing(socket.socket()) as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0


def kraft_config() -> Path:
    """Kafka 4.x moved the KRaft config; 3.x kept it under config/kraft/."""
    for c in (KAFKA_HOME / "config" / "server.properties",
              KAFKA_HOME / "config" / "kraft" / "server.properties"):
        if c.exists() and "process.roles" in c.read_text(encoding="utf-8"):
            return c
    raise RuntimeError("no KRaft server.properties found under ~/kafka/config")


@contextlib.contextmanager
def broker():
    """Start a single-node KRaft broker, yield, then stop it.

    KRaft means no ZooKeeper - the controller quorum lives in Kafka
    itself. Modern Kafka removed ZooKeeper entirely, so any tutorial
    that starts one is out of date.
    """
    if not (KAFKA_HOME / "bin" / "kafka-server-start.sh").exists():
        # DO NOT hardcode a version in this message. downloads.apache.org
        # serves only CURRENT releases: 4.0.0 was named here and now returns
        # HTTP 404, so anyone hitting this error followed a dead link. Tell
        # the reader how to DISCOVER the version instead.
        raise RuntimeError(
            f"Kafka not found at {KAFKA_HOME}.\n"
            "    # old releases are REMOVED from this mirror, so resolve the\n"
            "    # current one rather than pasting a version:\n"
            "    V=$(curl -s https://downloads.apache.org/kafka/ \\\n"
            "          | grep -oE '[0-9]+[.][0-9]+[.][0-9]+/' | tr -d / "
            "| sort -V | tail -1)\n"
            "    curl -fsSL "
            "https://downloads.apache.org/kafka/$V/kafka_2.13-$V.tgz | tar -xz\n"
            f"    mv kafka_2.13-$V {KAFKA_HOME}\n"
            f"    cd {KAFKA_HOME} && bin/kafka-storage.sh format "
            "-t $(bin/kafka-storage.sh random-uuid) "
            "-c config/server.properties --standalone")

    if port_open(9092):
        print("  Broker already running on :9092 - reusing it.\n")
        yield
        return

    cfg = kraft_config()
    print(f"  Starting Kafka broker on :9092  ({cfg.name}) ...")
    log = open("/tmp/kafka-broker.log", "w")
    proc = subprocess.Popen(
        [str(KAFKA_HOME / "bin" / "kafka-server-start.sh"), str(cfg)],
        stdout=log, stderr=subprocess.STDOUT)

    for _ in range(90):                      # the JVM takes a while
        if port_open(9092):
            break
        if proc.poll() is not None:
            log.close()
            tail = Path("/tmp/kafka-broker.log").read_text()[-600:]
            raise RuntimeError(f"broker exited during startup:\n{tail}")
        time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError("broker did not open :9092 within 45 s")

    time.sleep(2)                            # let metadata settle
    print("  Broker up.\n")
    try:
        yield
    finally:
        proc.terminate()
        with contextlib.suppress(Exception):
            proc.wait(timeout=30)
        log.close()
        print("\n  Broker stopped.")


# ============================================ 1. the distinction
def the_distinction() -> None:
    banner("1. The one distinction everything else follows from")

    print("  KAFKA        a topic is an ordered, replayable LOG, split into")
    print("               PARTITIONS. The consumer owns its position (the")
    print("               OFFSET). The broker stores messages for a retention")
    print("               period whether or not anyone read them.")
    print()
    print("  PUB/SUB      a subscription is a server-managed QUEUE. The")
    print("               broker tracks per-message acknowledgement. Once")
    print("               every subscription acks a message, it is gone.")

    print("\n  Almost every other difference is a consequence:")
    print("    - replay: Kafka rewinds an offset; Pub/Sub needs seek+snapshot")
    print("    - ordering: Kafka per partition; Pub/Sub per ordering key")
    print("    - parallelism: Kafka capped by partition count; Pub/Sub not")
    print("    - retention: Kafka time/size based; Pub/Sub until acked")
    print("    - ops: Kafka is a cluster you size; Pub/Sub has no dials")


# ============================================ 2. partitions
def partitions(admin) -> None:
    banner("2. Topics and PARTITIONS")

    from confluent_kafka.admin import NewTopic

    # START CLEAN - and the reason is itself the lesson.
    #
    # A Kafka log PERSISTS. Re-running this file against an existing
    # topic appends to what is already there, so the second run reads
    # both runs' messages and the numbers stop reproducing. An earlier
    # version did exactly that: 45 produced, 75 read, and the ordering
    # check went False because trip_ids from two runs interleaved.
    #
    # Pub/Sub would not behave this way - acked messages are gone. This
    # cleanup step exists *because* Kafka retains, which is the whole
    # distinction in section 1.
    if TOPIC in admin.list_topics(timeout=10).topics:
        print(f"  '{TOPIC}' already exists from a previous run - deleting, "
              f"because a Kafka log PERSISTS and would otherwise accumulate.")
        for _, f in admin.delete_topics([TOPIC]).items():
            with contextlib.suppress(Exception):
                f.result(timeout=30)
        for _ in range(30):                  # deletion is asynchronous
            if TOPIC not in admin.list_topics(timeout=10).topics:
                break
            time.sleep(0.5)

    fs = admin.create_topics([NewTopic(TOPIC, num_partitions=N_PARTITIONS,
                                       replication_factor=1)])
    for _, f in fs.items():
        f.result()
    for _ in range(30):                      # creation is asynchronous too
        if TOPIC in admin.list_topics(timeout=10).topics:
            break
        time.sleep(0.5)

    meta = admin.list_topics(timeout=10).topics[TOPIC]
    print(f"  topic '{TOPIC}' has {len(meta.partitions)} partitions: "
          f"{sorted(meta.partitions)}")

    print("\n  A PARTITION is the unit of ordering, parallelism, storage and")
    print("  replication all at once. Pub/Sub has no equivalent - which is")
    print("  why it has no number for you to choose, and also why it cannot")
    print("  offer you a total order over a subset of the stream.")

    print("\n  Partition count is the decision you cannot easily undo:")
    print("    - it CAPS consumer parallelism in a group (section 4)")
    print("    - you can add partitions, never remove them")
    print("    - adding them BREAKS existing key->partition mapping, so")
    print("      messages for a key start landing somewhere new and the")
    print("      per-key ordering guarantee is broken across the change")


# ============================================ 3. producing
def producing() -> tuple[int, dict[int, int]]:
    banner("3. Producing - and how a key decides the partition")

    from confluent_kafka import Producer

    p = Producer({"bootstrap.servers": BROKER, "linger.ms": 50})

    delivered: list[tuple[str, int]] = []

    def on_delivery(err, msg):
        if err is None:
            delivered.append((msg.key().decode(), msg.partition()))

    stations = [f"ST{i:02d}" for i in range(1, 10)]     # 9 keys
    for i in range(45):
        st = stations[i % len(stations)]
        p.produce(TOPIC, key=st.encode(),
                  value=f'{{"trip_id":"T{i:04d}","station":"{st}"}}'.encode(),
                  on_delivery=on_delivery)
    p.flush(30)

    by_station: dict[str, set[int]] = {}
    per_partition: dict[int, int] = {i: 0 for i in range(N_PARTITIONS)}
    for key, part in delivered:
        by_station.setdefault(key, set()).add(part)
        per_partition[part] += 1

    print(f"  produced and delivered {len(delivered)} messages "
          f"across {len(stations)} keys\n")
    print(f"  {'key':<8} {'partition(s)':<14} note")
    print("  " + "-" * 56)
    for st in stations:
        parts = sorted(by_station.get(st, []))
        note = "always the same" if len(parts) == 1 else "SPREAD - unexpected"
        print(f"  {st:<8} {str(parts):<14} {note}")

    print(f"\n  messages per partition: {dict(sorted(per_partition.items()))}")

    empty = [k for k, v in per_partition.items() if v == 0]
    biggest = max(per_partition.values())
    smallest = min(per_partition.values())
    print(f"  spread: {smallest} to {biggest} "
          f"({biggest / max(smallest, 1):.1f}x)")
    if empty:
        print(f"  ** partitions {empty} received NOTHING - real key skew **")

    print("\n  The key is hashed to choose a partition, so **the same key")
    print("  always lands on the same partition**. That is the entire")
    print("  mechanism behind Kafka's ordering guarantee.")
    print("\n  It is also the failure mode: the hash spreads KEYS evenly, not")
    print("  VOLUME. Few keys, or one busy key, and a partition is hot while")
    print("  another idles - measured above. Pub/Sub ordering keys have the")
    print("  same exposure; so does a Bigtable row key.")
    print("\n  No key at all means round-robin: good balance, no ordering.")
    return len(delivered), per_partition


# ============================================ 4. consumer groups
def consumer_groups() -> dict:
    banner("4. Consumer groups - the scaling unit, and its ceiling")

    from confluent_kafka import Consumer

    def drain(group: str, n_consumers: int) -> dict:
        """Run a group and report ASSIGNMENT as well as receipt.

        Assignment is the structural fact - how many consumers the group
        coordinator gave a partition to. Messages RECEIVED also depends
        on how the data was distributed, so a consumer can be assigned a
        partition and still get nothing if that partition is empty.
        Conflating the two is what made an earlier version of this
        section print 0 and then claim 'all active'.
        """
        consumers = [Consumer({
            "bootstrap.servers": BROKER,
            "group.id": group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
            "session.timeout.ms": 10000,
        }) for _ in range(n_consumers)]
        for c in consumers:
            c.subscribe([TOPIC])

        counts: dict[int, int] = {}
        total = 0
        # A first join has to wait for a group rebalance. Poll generously
        # rather than guessing - an impatient loop reports a false zero.
        deadline = time.time() + 30
        quiet = 0
        while time.time() < deadline and quiet < 12:
            got_any = False
            for idx, c in enumerate(consumers):
                msg = c.poll(0.25)
                if msg is not None and not msg.error():
                    counts[idx] = counts.get(idx, 0) + 1
                    total += 1
                    got_any = True
            quiet = 0 if got_any else quiet + 1

        assigned = {i: len(c.assignment()) for i, c in enumerate(consumers)}
        for c in consumers:
            c.close()
        return {"total": total, "received": counts, "assigned": assigned,
                "with_partitions": sum(1 for v in assigned.values() if v > 0)}

    r3 = drain("group-three", 3)
    print(f"  group of 3 consumers over {N_PARTITIONS} partitions")
    print(f"    partitions assigned : {dict(sorted(r3['assigned'].items()))}")
    print(f"    consumers with work : {r3['with_partitions']} of 3")
    print(f"    messages received   : {r3['total']}  "
          f"{dict(sorted(r3['received'].items()))}")

    r5 = drain("group-five", 5)
    print(f"\n  group of 5 consumers over {N_PARTITIONS} partitions")
    print(f"    partitions assigned : {dict(sorted(r5['assigned'].items()))}")
    print(f"    consumers with work : {r5['with_partitions']} of 5"
          f"   <- the ceiling")
    print(f"    messages received   : {r5['total']}  "
          f"{dict(sorted(r5['received'].items()))}")

    idle5 = 5 - r5["with_partitions"]
    print(f"\n  **A partition is assigned to at most ONE consumer in a group.**")
    print(f"  With {N_PARTITIONS} partitions, {idle5} of the 5 consumers were given")
    print("  nothing at all. They are not sharing the load - they are spare")
    print("  capacity waiting for a rebalance. Adding consumers past the")
    print("  partition count buys exactly nothing.")

    print("\n  Note the two numbers differ: a consumer can HOLD a partition")
    print("  and still receive nothing, if the key hash put no data there")
    print("  (section 3). Assignment is structural; receipt depends on skew.")

    print("\n  That ceiling is what Pub/Sub does not have: any number of")
    print("  subscribers pull from one subscription and the service load")
    print("  balances. The price is that Pub/Sub cannot promise an ordered")
    print("  log of a subset.")

    print(f"\n  Both groups read the SAME {r5['total']} messages. A different")
    print("  group.id gets its own offsets - Kafka's fan-out, and the")
    print("  equivalent of a second Pub/Sub subscription.")
    return {"three": r3, "five": r5}


# ============================================ 5. offsets and replay
def offsets_and_replay() -> tuple[int, int]:
    banner("5. OFFSETS and replay")

    from confluent_kafka import Consumer, TopicPartition

    def read_from_beginning(group: str) -> int:
        c = Consumer({"bootstrap.servers": BROKER, "group.id": group,
                      "auto.offset.reset": "earliest",
                      "enable.auto.commit": False})
        parts = [TopicPartition(TOPIC, i, 0) for i in range(N_PARTITIONS)]
        c.assign(parts)
        for tp in parts:
            c.seek(tp)                       # explicit rewind to offset 0
        n, idle = 0, 0
        while idle < 6:
            msg = c.poll(0.5)
            if msg is not None and not msg.error():
                n += 1; idle = 0
            else:
                idle += 1
        c.close()
        return n

    first = read_from_beginning("replay-demo")
    second = read_from_beginning("replay-demo")

    print(f"  read from offset 0        : {first} messages")
    print(f"  seek back to 0 and re-read: {second} messages")
    print(f"  identical: {first == second}")

    print("\n  **Nothing was consumed in the destructive sense.** Reading did")
    print("  not remove anything - the log is still there, and any consumer")
    print("  can set its offset back and read it again. That is replay, and")
    print("  it is the property teams most often say they cannot give up.")

    print("\n  Messages leave because of RETENTION - a time or size bound you")
    print("  configure - not because they were read. In Pub/Sub the opposite")
    print("  holds: a message is retained until every subscription acks it,")
    print("  and replay needs seek plus a snapshot taken in advance.")
    return first, second


# ============================================ 6. ordering
def ordering() -> bool:
    banner("6. Ordering: per partition, and nowhere else")

    from confluent_kafka import Consumer, TopicPartition

    c = Consumer({"bootstrap.servers": BROKER, "group.id": "order-demo",
                  "auto.offset.reset": "earliest", "enable.auto.commit": False})
    c.assign([TopicPartition(TOPIC, 0, 0)])

    seen: list[str] = []
    idle = 0
    while idle < 6:
        msg = c.poll(0.5)
        if msg is not None and not msg.error():
            seen.append(msg.value().decode()); idle = 0
        else:
            idle += 1
    c.close()

    ids = [s.split('"trip_id":"')[1].split('"')[0] for s in seen]
    ordered = ids == sorted(ids)
    print(f"  partition 0 held {len(ids)} messages")
    print(f"  first few: {ids[:6]}")
    print(f"  in produce order within this partition: {ordered}")

    print("\n  Within one partition, offsets are monotonic and order is")
    print("  absolute. ACROSS partitions there is no ordering at all - no")
    print("  global sequence exists, and asking for one means one partition,")
    print("  which means one consumer, which means no parallelism.")
    print("\n  Same trade as a Pub/Sub ordering key, arrived at from the")
    print("  other direction: order and parallelism are exchanged, always.")
    return ordered


# ============================================ 7. the decision
def the_decision() -> None:
    banner("7. Kafka or Pub/Sub")

    rows = [
        ("replay by offset, consumer-owned position", "Kafka"),
        ("already on Kafka, want less operational load", "Managed Kafka"),
        ("serverless, no capacity to plan", "Pub/Sub"),
        ("fan-out to many independent consumers", "either - both do it"),
        ("strict ordering over a large keyspace", "Kafka partitions"),
        ("unpredictable, spiky, global traffic", "Pub/Sub"),
        ("sub-10ms in-region latency, willing to run brokers", "Kafka"),
        ("straight into BigQuery with no pipeline", "Pub/Sub subscription"),
    ]
    print(f"  {'situation':<46} reach for")
    print("  " + "-" * 70)
    for a, b in rows:
        print(f"  {a:<46} {b}")

    print("\n  **Managed Service for Apache Kafka** is the middle option, and")
    print("  it is usually the right exam answer when a question says the")
    print("  customer has Kafka and wants to reduce operations WITHOUT a")
    print("  rewrite: it is real Kafka, so clients, Connect and offsets all")
    print("  keep working. Google runs the brokers; you still choose")
    print("  partitions and still think about consumer groups.")

    print("\n  Migrating to Pub/Sub instead is a genuine rewrite of consumer")
    print("  semantics - offsets become acks, replay becomes seek. The")
    print("  Pub/Sub Group Kafka Connector exists to bridge the two during a")
    print("  dual-write cutover, not to make them equivalent.")

    print("\n  >> The question to ask is never 'which is better'. It is")
    print("     'does this workload need a replayable log, or a queue?'")


def main() -> None:
    print("=" * 72)
    print("  KAFKA - the model, and how it differs from Pub/Sub".center(72))
    print("=" * 72)

    try:
        with broker():
            from confluent_kafka.admin import AdminClient
            admin = AdminClient({"bootstrap.servers": BROKER})

            the_distinction()
            partitions(admin)
            n_produced, per_part = producing()
            groups = consumer_groups()
            r1, r2 = offsets_and_replay()
            in_order = ordering()
            the_decision()

            # Every line below is derived from what was measured. An
            # earlier version hardcoded these and contradicted its own
            # output - the summary claimed "all active" where the
            # measurement had printed 0.
            g3, g5 = groups["three"], groups["five"]
            empty = [k for k, v in per_part.items() if v == 0]

            banner("Summary - all measured against a local broker")
            print(f"  - {n_produced} messages produced across "
                  f"{N_PARTITIONS} partitions: "
                  f"{dict(sorted(per_part.items()))}")
            print(f"  - a key always lands on the same partition"
                  + (f", but {len(empty)} partition(s) got nothing - key skew"
                     if empty else ""))
            print(f"  - 3 consumers / {N_PARTITIONS} partitions: "
                  f"{g3['with_partitions']} given work")
            print(f"  - 5 consumers / {N_PARTITIONS} partitions: "
                  f"{g5['with_partitions']} given work, "
                  f"{5 - g5['with_partitions']} idle")
            print(f"  - re-read from offset 0 twice: {r1} then {r2} - replay is free")
            print(f"  - order preserved within partition 0: {in_order}")
            print("\n  A Kafka partition is a replayable log with a")
            print("  consumer-owned offset. A Pub/Sub subscription is a")
            print("  server-managed queue with acks. Everything else follows.")

    except RuntimeError as e:
        print(f"\n  SKIPPED: {e}")
        sys.exit(0)


if __name__ == "__main__":
    main()
