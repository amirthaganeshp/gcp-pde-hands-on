# Bigtable — what the illustration shows

The README explains the *service*. This file explains the *script*: what it sets up, what it
measures, and — importantly — **which part is real and which part is a model that was wrong twice
before it was right**.

---

## `row_key_design.py`

**Setup:** the **official Bigtable emulator**, started and stopped by the script, with the real
`google-cloud-bigtable` 2.47.0 client. 4,000 trips written under four different row-key designs.

### Part A — read patterns (real, against the emulator)

| operation | rows | time |
|---|---|---|
| point read (exact key) | 1 | **1.6 ms** |
| prefix scan (`ST05#`) | 493 | **68 ms** |
| **full table scan** | 4,000 | **490 ms** |

**The point read and prefix scan are cheap because matching rows are physically adjacent** — that
is what "sorted by row key" buys you. The full scan is what *every query that does not match the
row key* becomes, because there is no second index to fall back on.

### Part B — write distribution (a model, see below)

4,000 trips arriving **in time order**, 8 tablets. For each burst of 100 consecutive writes, how
many distinct tablets received them?

| design | tablets per burst | worst burst | spread |
|---|---|---|---|
| `timestamp#trip_id` | **1.0** | 1 | **12%** |
| `station#timestamp` | 7.9 | 7 | 99% |
| `station#~timestamp` | 7.9 | 6 | 99% |
| `hash#station#timestamp` | 8.0 | 8 | 100% |

## The headline: 1.0 of 8

**A timestamp-first key sent every concurrent write to a single tablet on a single node**, while
the other seven sat idle. That is hot-spotting, and the number is as bad as it can possibly be.

> **It is invisible in testing.** A small dataset fits in one tablet regardless, so the design only
> fails at the scale you bought Bigtable for — and by then the row key **cannot be changed**.

## Field promotion vs salting — the 7.9 vs 8.0

Moving `station` to the front took the spread from 12% to **99%**. Salting reached 100%. That last
point of improvement costs a great deal:

> **Salting destroys range scans.** With `hash#station#time` the hash is leftmost, so reading one
> station means scanning **every salt bucket** — a cheap prefix scan becomes a fan-out. Salt only
> when the access pattern is genuinely point reads. If you range-scan, promote a real field.

`station#~timestamp` (reversed timestamp) keeps the prefix *and* sorts newest-first, so "latest N
for this station" is a prefix scan with a limit rather than scan-and-sort.

## The honest part: the tablet model was wrong twice

**Part B is a simulation.** Tablets are modelled by splitting the *sorted key space* into 8 ranges
at quantiles of the actual keys — which is what real Bigtable does when it splits to balance
storage.

The first version used `ord(key[0]) % 8`, and it was **wrong in two independent ways**:

1. It looked only at the **first byte**, so every `ST..` key landed on one tablet and
   **station-first scored as badly as timestamp-first** — erasing the entire finding.
2. It measured where rows come to **rest**, when hot-spotting is about where concurrent **writes**
   land.

The current version measures **distinct tablets per burst of 100 consecutive writes, in arrival
order**, which is the thing that actually hurts. Recorded in
[`99_reference/FINDINGS.md`](../../../99_reference/FINDINGS.md) §8.

## What the emulator cannot show

Not demonstrated, and not simulated: real tablet splitting and rebalancing, node scaling,
replication and app-profile routing, SSD vs HDD performance, garbage-collection policies executing,
or Key Visualizer. The emulator has one node and no notion of a cluster.

**What is real** is the read-pattern timing and the key-sorting behaviour — and those are what the
design rules follow from.
