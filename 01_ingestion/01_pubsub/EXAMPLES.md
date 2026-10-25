# Pub/Sub — what the illustration shows

The README explains the *service*. This file explains the *script*: what it sets up, what it
measures, and which exam idea each measurement makes concrete.

---

## `pubsub_basics.py`

**Setup:** the script starts the **official Pub/Sub emulator**, runs six sections against it, and
stops it again. No project, no credentials, no billing — and the client library is the real
`google-cloud-pubsub` **2.41.0**, unmodified.

| § | it does | measured | the exam idea |
|---|---|---|---|
| 1 | creates one topic and **two** subscriptions | both listed | **a topic is not a queue** — each subscription holds its own copy |
| 2 | publishes 10, pulls 10, acks 10 | 10 / 10 / 10 | the ack is the contract |
| 3 | **pulls one and refuses to ack it** | the **same message** returns after 10 s | **at-least-once is not an error condition** |
| 4 | publishes 5 with an ordering key | order preserved | ordering is **per key**, never global |
| 5 | attaches a dead-letter policy | DLQ after 5 attempts | poison messages leave the pipeline |
| 6 | reprocesses a duplicate idempotently | same final state | the design consequence of §3 |

## §3 is the one that matters

```
pull   -> message M
(do not acknowledge)
wait   -> 10 second ack deadline expires
pull   -> message M        <- identical payload, nothing having failed
```

**Nothing went wrong here.** Pub/Sub leased the message, the lease expired without an ack, and it
correctly assumed the subscriber had died. This is the single largest source of "duplicate
messages" in production.

> The fix is **not** a longer ack deadline. It is to **ack promptly**, **extend the lease** while
> genuinely still working (`modifyAckDeadline`), and make the handler **idempotent** — which is why
> §6 exists and why every sink in this repo uses `MERGE` rather than `INSERT`.

## What the emulator cannot show

The emulator is real Pub/Sub semantics for the basics and **silent about the rest**. Not
demonstrated anywhere here, and not simulated:

| | why |
|---|---|
| **exactly-once delivery** | regional dedup is a service feature |
| **push subscriptions** | needs a reachable HTTPS endpoint |
| **BigQuery / GCS subscriptions** | needs the real sinks |
| **seek and snapshots** | not implemented in the emulator |
| **schema enforcement** | not implemented |
| **quota and throughput behaviour** | one process on one laptop proves nothing about it |

## The environment trap that cost real time

```python
def find_gcloud() -> str:
    if os.path.exists("/usr/bin/gcloud"):
        return "/usr/bin/gcloud"
    found = shutil.which("gcloud")
    if found and found.startswith("/mnt/"):
        raise RuntimeError("the only gcloud on PATH is a WINDOWS install ...")
```

**WSL puts the Windows PATH on the Linux PATH.** `which gcloud` returned a *Windows* SDK under
`/mnt/c`, which cannot run the emulator and fails with a traceback from the Windows Python — which
reads as a bug in your script. The script refuses that path explicitly rather than failing
mysteriously.
