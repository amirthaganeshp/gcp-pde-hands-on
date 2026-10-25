# Cloud Storage — what the illustration shows

The README explains the *service*. This file explains the *script*: what it computes, and why the
storage class is arithmetic rather than a judgement call.

---

## `storage_class_cost.py`

**Setup:** pure Python. No bucket, no cloud, no billing — it evaluates the published pricing model
over a matrix of object sizes and monthly read counts.

**This is a computation, not a simulation.** There is no fake API and nothing pretends to be GCS.
The prices are approximate US multi-region list prices and **they move** — the script prints them
so a stale number is visible rather than hidden.

| § | it does | measured |
|---|---|---|
| 1 | prices the four classes side by side | Standard 0.0260 · Nearline 0.0100 · Coldline 0.0040 · Archive 0.0012 $/GB/mo |
| 2 | solves for the read rate where two classes cost the same | **1.60 / 0.60 / 0.09** reads per month |
| 3 | prices 1 TB read once a month, all four ways | Nearline **$20.48** · Coldline **$24.58** · **Archive $52.43** |
| 4 | applies minimum-duration charges to a short-lived object | Archive **17× worse** than Standard for one day |

## The crossovers are the whole point

| pair | crosses at |
|---|---|
| Standard vs Nearline | **1.60 reads/month** |
| Nearline vs Coldline | 0.60 reads/month |
| Coldline vs Archive | 0.09 reads/month |

**Below the crossover the colder class wins; above it, the warmer one does.** Standard beats
Nearline once data is read more than **1.6 times a month** — which for anything a dashboard touches
is every single day.

## The result that reverses the intuition

```
1 TB, read once per month:
  Nearline  $20.48
  Coldline  $24.58
  Archive   $52.43      <- roughly TWICE Standard
```

**Archive is the most expensive option here**, despite having the cheapest storage price by a
factor of twenty. Retrieval at $0.050/GB dominates everything else the moment the data is actually
read.

> **Reasoning from the storage price alone gets this exactly backwards**, and that is the trap.
> "Move it to Archive to save money" is correct only for data nobody reads.

## Minimum durations are a second trap

Archive bills a **365-day minimum**. An object deleted after one day is charged for a year — so for
short-lived data the cheapest class is **17× worse** than the most expensive one.

**Lifecycle rules plus minimum durations interact badly**: a rule that moves objects to Coldline at
30 days and deletes them at 60 pays a 90-day minimum on every object for 30 days of storage. And
because lifecycle rules are evaluated in parallel with **the most destructive action winning**, two
sensible-looking rules can quietly become "delete" — see README §5.

## What this cannot show

Not demonstrated: actual bucket operations, lifecycle rules firing, Autoclass behaviour over time,
retention locks, soft-delete restores, or real retrieval latency. Those need a project and, for
some of them, months of elapsed time.

**What transfers completely is the arithmetic** — the crossover formula is the same wherever the
prices land.
