# Transfer — what the illustration shows

The README explains the *services*. This file explains the *script* — which is deliberately the
smallest one in the repository, because the decision it models is division.

---

## `transfer_decision.py`

**Setup:** pure Python. A matrix of data volumes against link speeds, with the Transfer Appliance
crossover solved for.

**This is a computation, not a simulation.** Nothing pretends to be an API.

| § | it does | measured |
|---|---|---|
| 1 | times a fixed volume across link speeds | 100 TB: **132 days** @ 100 Mbps · ~13 days @ 1 Gbps · **1 day** @ 10 Gbps |
| 2 | solves for where an appliance beats the wire | **~106 TB** @ 1 Gbps (**~10.6 TB** @ 100 Mbps) |
| 3 | applies a realistic utilisation factor | the same job takes materially longer than nominal |

## The point: volume alone never decides this

```
100 TB over 100 Mbps  = 132 days
100 TB over 10 Gbps   =   1 day
```

**Same data. Two orders of magnitude.** A question that gives you a volume without a bandwidth is
incomplete, and "100 TB is a lot" is not an answer — it is trivial on a Dedicated Interconnect and
impossible on a branch-office line.

```
days = bytes / (usable bandwidth x seconds per day)
```

## §3 — usable bandwidth is not link speed

The link is shared with the business, TCP over a long-haul path rarely reaches line rate, and a
migration that saturates the corporate uplink is an outage.

> **Planning at 100% of nominal capacity is how a 13-day estimate becomes 40.** The script applies
> a utilisation factor for exactly this reason, and the gap between the two numbers is the lesson.

## Two things the arithmetic does not include

**The appliance's clock includes shipping.** Transit each way, plus load time and Google-side
upload — not the raw copy duration. For a genuinely marginal case the online path often wins on
*elapsed* time even when it loses on throughput.

**Offline transfer is one-shot, and the source keeps changing.** An appliance captures a point in
time; everything written while it is in transit needs a catch-up. That catch-up is CDC — which is
why [`../01_datastream/`](../01_datastream/) sits in the same section.

## The narration bug this script caught

An earlier version described a 132-day transfer as taking **"over three years"** — the unit
threshold for switching from days to years was wrong, and the sentence was written before the
number was read. Recorded in
[`99_reference/FINDINGS.md`](../../99_reference/FINDINGS.md) §8.

> Every narrated line is now derived from the computed value rather than written alongside it.

## What is not demonstrated

Storage Transfer Service agents, the appliance request-and-ship workflow, Interconnect
provisioning, or DTS schedules. There is nothing to simulate: **the decision is the arithmetic, and
the arithmetic is real.**
