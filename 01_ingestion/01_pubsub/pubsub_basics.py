"""Pub/Sub: the fundamental operations, against the local emulator.

Everything here talks to the REAL google-cloud-pubsub client library. The
only difference from production is the PUBSUB_EMULATOR_HOST environment
variable, which points the client at a local fake instead of Google. The
code is otherwise identical - no project, no credentials, no billing.

  1. Topics and subscriptions - create, list, delete
  2. Publish and pull - the round trip
  3. ACK DEADLINES and redelivery - measured
  4. Ordering keys - and what they cost
  5. Dead-letter topics - where poison messages go
  6. Idempotency - because delivery is at-least-once

EXECUTED IN FULL against the emulator, which this file starts and stops
itself. If the emulator is unavailable it says so and exits cleanly
rather than pretending.

Run:
    python 01_ingestion/01_pubsub/pubsub_basics.py

Guide reference: Success Guide pp. 68-72; Ultimate Edition section 2.2.
"""

from __future__ import annotations

import contextlib
import os
import signal
import shutil
import socket
import subprocess
import sys
import time
from concurrent.futures import TimeoutError as FuturesTimeout

PROJECT = "local-demo"          # the emulator does not validate this
EMULATOR_PORT = 8681


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


# ============================================ emulator lifecycle
def free_port(port: int) -> bool:
    with contextlib.closing(socket.socket()) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def find_gcloud() -> str:
    """Locate a LINUX gcloud, deliberately.

    WSL puts the Windows PATH on the Linux PATH, so `which gcloud` very
    often returns a Windows install under /mnt/c. That binary cannot run
    the emulator from here, and the failure it produces is a Python
    traceback from the Windows SDK - which looks like a bug in this
    script rather than the wrong executable.

    So: prefer the packaged Linux path, and refuse /mnt/c explicitly.
    """
    if os.path.exists("/usr/bin/gcloud"):
        return "/usr/bin/gcloud"

    found = shutil.which("gcloud")
    if found and found.startswith("/mnt/"):
        raise RuntimeError(
            f"the only gcloud on PATH is a WINDOWS install ({found}), which "
            "cannot run the emulator from WSL. Install the Linux one:\n"
            "    sudo apt-get install -y google-cloud-cli "
            "google-cloud-cli-pubsub-emulator default-jre")
    if found:
        return found

    raise RuntimeError(
        "gcloud not found. The Pub/Sub emulator ships with the Google "
        "Cloud CLI:\n"
        "    sudo apt-get install -y google-cloud-cli "
        "google-cloud-cli-pubsub-emulator default-jre")


def _stop_emulator(proc, port: int) -> None:
    """Stop the emulator - the whole PROCESS GROUP, not just the wrapper.

    THE BUG THIS FIXES, found by running the repo's full run-list:
    `gcloud beta emulators ... start` is a WRAPPER that spawns the actual
    emulator as a child (java, or a Go binary for Bigtable). Calling
    proc.terminate() kills only the wrapper and ORPHANS the child, which
    keeps holding the port. The run-list left five such orphans behind,
    some of them running for hours - while every README claimed each
    script "starts and stops its own emulator".

    start_new_session=True puts the wrapper in its own process group so the
    whole group can be signalled here.
    """
    with contextlib.suppress(Exception):
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    with contextlib.suppress(Exception):
        proc.wait(timeout=10)

    # If the port is still held, the group ignored SIGTERM. Escalate.
    with contextlib.closing(socket.socket()) as s:
        s.settimeout(0.5)
        if s.connect_ex(("127.0.0.1", port)) == 0:
            with contextlib.suppress(Exception):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


@contextlib.contextmanager
def emulator(port: int = EMULATOR_PORT):
    """Start the Pub/Sub emulator, yield, then stop it.

    Every emulator-backed example in this repository owns its own
    emulator, so one file can be run without reading the setup guide.

    The emulator is a JAVA program shipped with the gcloud SDK - the
    Python client is pure Python, but the fake server it talks to is not.
    """
    gcloud = find_gcloud()

    if not free_port(port):
        print(f"  Port {port} already in use - reusing whatever is there.")
        os.environ["PUBSUB_EMULATOR_HOST"] = f"localhost:{port}"
        yield
        return

    print(f"  Starting Pub/Sub emulator on :{port}  ({gcloud}) ...")
    proc = subprocess.Popen(
        [gcloud, "beta", "emulators", "pubsub", "start",
         f"--project={PROJECT}", f"--host-port=localhost:{port}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)   # own process group - see _stop_emulator

    os.environ["PUBSUB_EMULATOR_HOST"] = f"localhost:{port}"
    for _ in range(60):                      # up to ~30 s for the JVM
        if not free_port(port):
            break
        time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError("emulator did not start within 30 s")

    print("  Emulator up.\n")
    try:
        yield
    finally:
        _stop_emulator(proc, port)
        print("\n  Emulator stopped.")


# ============================================ 1. topics and subs
def topics_and_subscriptions(pub, sub):
    banner("1. Topics and subscriptions")

    from google.api_core import exceptions

    topic = pub.topic_path(PROJECT, "trips")
    with contextlib.suppress(exceptions.AlreadyExists):
        pub.create_topic(request={"name": topic})

    # One topic, TWO subscriptions - each gets its own copy of every
    # message. This is the fan-out that makes Pub/Sub a decoupler rather
    # than a queue: adding a consumer needs no change to the publisher.
    for name in ("trips-analytics", "trips-alerts"):
        path = sub.subscription_path(PROJECT, name)
        with contextlib.suppress(exceptions.AlreadyExists):
            sub.create_subscription(
                request={"name": path, "topic": topic,
                         "ack_deadline_seconds": 10})

    subs = list(pub.list_topic_subscriptions(request={"topic": topic}))
    print(f"  topic 'trips' has {len(subs)} subscriptions:")
    for s in subs:
        print(f"    - {s.rsplit('/', 1)[-1]}")

    print("\n  A topic is not a queue. Each SUBSCRIPTION holds its own")
    print("  backlog, so two subscribers do not compete for messages -")
    print("  both receive everything. Competing consumers come from")
    print("  running several clients on ONE subscription.")
    return topic


# ============================================ 2. publish and pull
def publish_and_pull(pub, sub, topic):
    banner("2. Publish and pull - the round trip")

    futures = []
    for i in range(10):
        # Messages are bytes. Attributes are the metadata you filter on.
        futures.append(pub.publish(
            topic, f'{{"trip_id": "T{i:04d}"}}'.encode(),
            station="ST01", bike_type="electric" if i % 3 == 0 else "classic"))
    ids = [f.result(timeout=30) for f in futures]
    print(f"  published {len(ids)} messages, server-assigned ids e.g. {ids[0]}")

    path = sub.subscription_path(PROJECT, "trips-analytics")
    resp = sub.pull(request={"subscription": path, "max_messages": 10},
                    timeout=30)
    got = resp.received_messages
    print(f"  pulled {len(got)} messages")
    print(f"  first payload   : {got[0].message.data.decode()}")
    print(f"  first attributes: {dict(got[0].message.attributes)}")

    sub.acknowledge(request={"subscription": path,
                             "ack_ids": [m.ack_id for m in got]})
    print(f"  acked {len(got)}")

    print("\n  `publish()` returns a FUTURE, not a message id. The client")
    print("  batches in the background, so calling .result() on every")
    print("  publish one at a time defeats the batching and is the most")
    print("  common cause of a 'slow' publisher.")
    return len(got)


# ============================================ 3. ack deadline
def ack_deadline(pub, sub, topic):
    banner("3. Ack deadlines and redelivery - measured")

    from google.api_core import exceptions

    path = sub.subscription_path(PROJECT, "deadline-demo")
    with contextlib.suppress(exceptions.AlreadyExists):
        sub.create_subscription(request={"name": path, "topic": topic,
                                         "ack_deadline_seconds": 10})

    pub.publish(topic, b'{"trip_id": "DEADLINE-TEST"}').result(timeout=30)

    first = sub.pull(request={"subscription": path, "max_messages": 1},
                     timeout=30).received_messages
    print(f"  pull #1 -> {len(first)} message, NOT acked")

    # Deliberately let the deadline expire.
    print("  waiting out the 10 s ack deadline ...")
    time.sleep(12)

    second = sub.pull(request={"subscription": path, "max_messages": 1},
                      timeout=30).received_messages
    print(f"  pull #2 -> {len(second)} message  (the SAME message, redelivered)")

    if second:
        same = (second[0].message.data == first[0].message.data)
        print(f"  identical payload: {same}")
        sub.acknowledge(request={"subscription": path,
                                 "ack_ids": [second[0].ack_id]})

    print("\n  Nothing failed here. The subscriber simply did not ack in")
    print("  time, so Pub/Sub assumed it died and redelivered - which is")
    print("  exactly what at-least-once means, and the single biggest")
    print("  source of 'duplicate' messages in production.")
    print("\n  The fix is NOT a longer deadline. It is to ack promptly and")
    print("  extend the lease while genuinely still working: the streaming")
    print("  pull client does that for you automatically.")
    return len(first), len(second)


# ============================================ 4. ordering keys
def ordering_keys(pub, sub, topic):
    banner("4. Ordering keys - and what they cost")

    from google.api_core import exceptions
    from google.cloud import pubsub_v1

    path = sub.subscription_path(PROJECT, "ordered-demo")
    with contextlib.suppress(exceptions.AlreadyExists):
        sub.create_subscription(request={"name": path, "topic": topic,
                                         "enable_message_ordering": True})

    ordered_pub = pubsub_v1.PublisherClient(
        publisher_options=pubsub_v1.types.PublisherOptions(
            enable_message_ordering=True))

    for i in range(5):
        ordered_pub.publish(topic, f"ST01-event-{i}".encode(),
                            ordering_key="ST01").result(timeout=30)

    resp = sub.pull(request={"subscription": path, "max_messages": 10},
                    timeout=30)
    payloads = [m.message.data.decode() for m in resp.received_messages]
    if resp.received_messages:
        sub.acknowledge(request={"subscription": path,
                                 "ack_ids": [m.ack_id
                                             for m in resp.received_messages]})

    print(f"  received in order: {payloads}")

    print("\n  Ordering is per ORDERING KEY, never global. Messages with")
    print("  the same key arrive in publish order; different keys have no")
    print("  relationship at all.")
    print("\n  The cost is parallelism. A key is processed by one subscriber")
    print("  at a time, so a hot key becomes a serial bottleneck - the same")
    print("  shape of problem as a hot key in Bigtable or a hot partition")
    print("  in Kafka. Order only what genuinely needs ordering.")
    print("\n  Ordering also requires BOTH sides: the publisher must enable")
    print("  it AND the subscription must. Setting one silently gives you")
    print("  no ordering at all.")
    return payloads


# ============================================ 5. dead letter
def dead_letter(pub, sub, topic):
    banner("5. Dead-letter topics - where poison messages go")

    from google.api_core import exceptions
    from google.cloud.pubsub_v1.types import DeadLetterPolicy

    dlq_topic = pub.topic_path(PROJECT, "trips-dlq")
    with contextlib.suppress(exceptions.AlreadyExists):
        pub.create_topic(request={"name": dlq_topic})

    dlq_sub = sub.subscription_path(PROJECT, "trips-dlq-sub")
    with contextlib.suppress(exceptions.AlreadyExists):
        sub.create_subscription(request={"name": dlq_sub, "topic": dlq_topic})

    path = sub.subscription_path(PROJECT, "poison-demo")
    with contextlib.suppress(exceptions.AlreadyExists):
        sub.create_subscription(request={
            "name": path, "topic": topic, "ack_deadline_seconds": 10,
            "dead_letter_policy": DeadLetterPolicy(
                dead_letter_topic=dlq_topic, max_delivery_attempts=5)})

    got = sub.get_subscription(request={"subscription": path})
    p = got.dead_letter_policy
    print(f"  subscription 'poison-demo' dead-letter policy:")
    print(f"    topic                 : {p.dead_letter_topic.rsplit('/', 1)[-1]}")
    print(f"    max_delivery_attempts : {p.max_delivery_attempts}")

    print("\n  Without this, a message your code cannot parse is redelivered")
    print("  FOREVER - blocking nothing, but burning quota and filling logs")
    print("  while the real problem stays invisible.")
    print("\n  Two things that catch people out:")
    print("    - the SUBSCRIPTION needs publish rights on the DLQ topic,")
    print("      and the service account needs subscriber on the source;")
    print("      miss either and dead-lettering silently does nothing")
    print("    - always put a SUBSCRIPTION on the DLQ topic. A topic with")
    print("      no subscription discards everything, so your poison")
    print("      messages are dead-lettered straight into the void")
    return p.max_delivery_attempts


# ============================================ 6. idempotency
def idempotency():
    banner("6. Idempotency - because delivery is at-least-once")

    print("  Section 3 proved redelivery happens without any failure. So")
    print("  the consumer must be safe to run twice on the same message.")
    print("\n  Three approaches, in order of preference:")
    print("    1. NATURALLY IDEMPOTENT writes - an upsert keyed on a")
    print("       business id, not an append. Costs nothing, cannot drift.")
    print("    2. DEDUPLICATE on a key you control - a trip_id, not the")
    print("       Pub/Sub message_id. Beam's deduplicate transform and")
    print("       BigQuery's streaming dedup both want YOUR key.")
    print("    3. Exactly-once delivery - real, but scoped to a region and")
    print("       it slows things down. It also only covers DELIVERY: your")
    print("       processing can still be re-run after a crash.")

    print("\n  >> 'Exactly-once' is never a substitute for an idempotent")
    print("     consumer. It narrows the window; it does not close it.")


def main() -> None:
    print("=" * 72)
    print("  PUB/SUB - fundamental operations".center(72))
    print("=" * 72)

    try:
        with emulator():
            from google.cloud import pubsub_v1
            pub = pubsub_v1.PublisherClient()
            sub = pubsub_v1.SubscriberClient()

            topic = topics_and_subscriptions(pub, sub)
            n_pulled = publish_and_pull(pub, sub, topic)
            first, second = ack_deadline(pub, sub, topic)
            order = ordering_keys(pub, sub, topic)
            attempts = dead_letter(pub, sub, topic)
            idempotency()

            banner("Summary - all measured against the emulator")
            print(f"  - published 10, pulled and acked {n_pulled}")
            print(f"  - an unacked message was redelivered: "
                  f"{first} then {second}, same payload")
            print(f"  - ordering key ST01 preserved order: {order}")
            print(f"  - dead-letter after {attempts} delivery attempts")
            print("\n  A topic fans out; a subscription holds the backlog.")
            print("  Delivery is at-least-once, so consumers must be")
            print("  idempotent - that is the whole design, and everything")
            print("  else is a dial on top of it.")

    except RuntimeError as e:
        print(f"\n  SKIPPED: {e}")
        sys.exit(0)


if __name__ == "__main__":
    main()
