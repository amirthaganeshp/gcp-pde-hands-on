"""BigQuery economics: on-demand or capacity, and logical or physical.

Two pricing decisions the exam asks about, both of which are crossovers
you can compute rather than opinions you hold.

  1. Compute: on-demand ($/TiB scanned) vs capacity ($/slot-hour)
  2. The crossover, and why committed slots move it
  3. Storage: active vs LONG-TERM, which is automatic and free
  4. Storage: LOGICAL vs PHYSICAL billing - a compression bet
  5. The cost controls that actually stop a bill

EXECUTED IN FULL. Arithmetic only.

** PRICES ARE APPROXIMATE ** US multi-region list prices at time of
writing. They move. The method is the point.

Run:
    python 11_ops_cost_monitoring/01_cost/bigquery_economics.py

Guide reference: Success Guide pp. 36-37, 48-50; Ultimate Edition
sections 5.1 and 5.3.
"""

from __future__ import annotations

# --- compute ---------------------------------------------------------
ON_DEMAND_PER_TIB = 6.25          # $ per TiB scanned
FREE_TIB_PER_MONTH = 1.0          # first TiB each month is free

# Editions, $ per slot-hour, pay-as-you-go
EDITIONS = {
    "Standard":        0.04,
    "Enterprise":      0.06,
    "Enterprise Plus": 0.10,
}
# Commitment discounts off the pay-as-you-go slot-hour rate
COMMITMENTS = {"none": 0.00, "1 year": 0.20, "3 years": 0.40}

HOURS_PER_MONTH = 730

# --- storage ---------------------------------------------------------
LOGICAL_ACTIVE = 0.020            # $ per GiB per month
LOGICAL_LONG_TERM = 0.010         # after 90 days untouched - automatic
PHYSICAL_ACTIVE = 0.040           # per GiB of COMPRESSED bytes
PHYSICAL_LONG_TERM = 0.020


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


# ============================================ 1-2. compute
def compute_crossover() -> dict:
    banner("1-2. On-demand or capacity?")

    print(f"  on-demand        ${ON_DEMAND_PER_TIB:.2f} per TiB scanned, "
          f"first {FREE_TIB_PER_MONTH:.0f} TiB/month free")
    print(f"  Enterprise slots ${EDITIONS['Enterprise']:.2f} per slot-hour, "
          f"billed while the reservation exists\n")

    print("  **The shapes are different, which is the whole point.**")
    print("  On-demand bills WORK DONE. Capacity bills TIME RESERVED - a")
    print("  reservation costs the same whether it is saturated or idle.\n")

    slots = 100
    monthly_slot_cost = slots * EDITIONS["Enterprise"] * HOURS_PER_MONTH

    print(f"  {slots} Enterprise slots, always on:")
    print(f"    {slots} x ${EDITIONS['Enterprise']:.2f} x {HOURS_PER_MONTH} h "
          f"= ${monthly_slot_cost:,.0f} / month\n")

    print(f"  {'TiB scanned/month':>19} {'on-demand':>12} "
          f"{f'{slots} slots':>12}   cheaper")
    print("  " + "-" * 60)

    out = {}
    for tib in (1, 5, 20, 50, 100, 200, 500):
        od = max(0.0, tib - FREE_TIB_PER_MONTH) * ON_DEMAND_PER_TIB
        cheaper = "on-demand" if od < monthly_slot_cost else "capacity"
        out[tib] = {"on_demand": od, "capacity": monthly_slot_cost,
                    "cheaper": cheaper}
        print(f"  {tib:>19,} {'$' + format(od, ',.0f'):>12} "
              f"{'$' + format(monthly_slot_cost, ',.0f'):>12}   {cheaper}")

    # where they cross
    crossover_tib = monthly_slot_cost / ON_DEMAND_PER_TIB + FREE_TIB_PER_MONTH
    print(f"\n  crossover: **{crossover_tib:,.0f} TiB scanned per month**")

    print("\n  Below that, on-demand wins and a reservation is paying for")
    print("  idle slots. Above it, capacity wins and on-demand is paying a")
    print("  premium for elasticity you are not using.")

    banner("What commitments do to the crossover")

    print(f"  {'commitment':<12} {'$/slot-hour':>13} {'$/month':>12} "
          f"{'crossover TiB':>15}")
    print("  " + "-" * 56)
    commits = {}
    for name, discount in COMMITMENTS.items():
        rate = EDITIONS["Enterprise"] * (1 - discount)
        monthly = slots * rate * HOURS_PER_MONTH
        cross = monthly / ON_DEMAND_PER_TIB + FREE_TIB_PER_MONTH
        commits[name] = {"rate": rate, "monthly": monthly, "crossover": cross}
        print(f"  {name:<12} {rate:>13.3f} {'$' + format(monthly, ',.0f'):>12} "
              f"{cross:>15,.0f}")

    print("\n  **A commitment lowers the crossover**, so it favours capacity")
    print("  at a smaller workload - but it is a commitment: you pay it")
    print("  whether or not you use it, for a year or three.")

    print("\n  The real-world answer is usually BOTH: a baseline reservation")
    print("  sized to the steady load, with on-demand or autoscaling slots")
    print("  absorbing the peaks. Sizing a reservation for the peak is how")
    print("  people end up paying for idle slots all night.")
    return {"crossover": crossover_tib, "by_volume": out,
            "commitments": commits, "monthly_slot_cost": monthly_slot_cost}


# ============================================ 3. long-term storage
def long_term_storage() -> dict:
    banner("3. Active vs long-term storage - automatic, and free")

    gib = 10_000       # 10 TiB

    active = gib * LOGICAL_ACTIVE
    longterm = gib * LOGICAL_LONG_TERM

    print(f"  {gib:,} GiB held for a month:\n")
    print(f"    active (modified within 90 days)  ${active:>9,.2f}")
    print(f"    long-term (untouched 90+ days)    ${longterm:>9,.2f}")
    print(f"    saving                            {1 - longterm / active:>9.0%}")

    print("\n  **This happens automatically and costs nothing to enable.**")
    print("  A table partition not MODIFIED for 90 days drops to long-term")
    print("  pricing. Reading it does not reset the clock - only writing")
    print("  does.")

    print("\n  Which is the trap: a pipeline that rewrites a whole table")
    print("  daily keeps every byte at active pricing forever. The same")
    print("  data, written as date partitions where only today's partition")
    print("  changes, lets everything older age into the discount.")
    print("\n  **Partitioning is a storage-cost decision as well as a query-")
    print("  cost one**, and that is not obvious from either price list.")
    return {"active": active, "long_term": longterm}


# ============================================ 4. logical vs physical
def logical_vs_physical() -> dict:
    banner("4. Logical or physical storage billing - a bet on compression")

    print(f"  logical  ${LOGICAL_ACTIVE:.3f}/GiB active, "
          f"${LOGICAL_LONG_TERM:.3f} long-term  (UNCOMPRESSED bytes)")
    print(f"  physical ${PHYSICAL_ACTIVE:.3f}/GiB active, "
          f"${PHYSICAL_LONG_TERM:.3f} long-term  (COMPRESSED bytes)\n")

    print("  Physical costs 2x per GiB - but bills the compressed size, so")
    print("  it wins whenever your data compresses better than 2x.\n")

    logical_gib = 10_000
    print(f"  {'compression':>13} {'physical GiB':>14} {'logical $':>11} "
          f"{'physical $':>12}   cheaper")
    print("  " + "-" * 66)

    out = {}
    for ratio in (1.5, 2.0, 3.0, 5.0, 10.0):
        phys_gib = logical_gib / ratio
        lo = logical_gib * LOGICAL_ACTIVE
        ph = phys_gib * PHYSICAL_ACTIVE
        cheaper = "logical" if lo <= ph else "PHYSICAL"
        out[ratio] = {"logical": lo, "physical": ph, "cheaper": cheaper}
        print(f"  {ratio:>12.1f}x {phys_gib:>14,.0f} "
              f"{'$' + format(lo, ',.0f'):>11} "
              f"{'$' + format(ph, ',.0f'):>12}   {cheaper}")

    print(f"\n  crossover: **{PHYSICAL_ACTIVE / LOGICAL_ACTIVE:.1f}x "
          f"compression**")

    print("\n  Typical analytical data compresses 3-5x, so physical billing")
    print("  is often the better choice - and it is per-DATASET, opt-in,")
    print("  and reversible only after a waiting period.")

    print("\n  Measure before switching. `INFORMATION_SCHEMA.TABLE_STORAGE`")
    print("  gives both numbers, so the ratio is a query rather than a")
    print("  guess:")
    print("      total_logical_bytes / total_physical_bytes")
    return out


# ============================================ 5. controls
def controls() -> None:
    banner("5. The controls that actually stop a bill")

    rows = [
        ("require_partition_filter", "table option", "rejects an unfiltered query outright"),
        ("maximum_bytes_billed", "per query", "the job FAILS rather than overspends"),
        ("custom quota", "per project/user/day", "a daily ceiling on bytes"),
        ("reservation", "per assignment", "a hard cap on concurrent compute"),
        ("dry run", "before running", "free - tells you the bytes first"),
        ("budget alert", "after the fact", "notifies; does NOT stop anything"),
    ]
    print(f"  {'control':<26} {'scope':<22} effect")
    print("  " + "-" * 74)
    for a, b, c in rows:
        print(f"  {a:<26} {b:<22} {c}")

    print("\n  **Only the first four prevent spend.** A budget alert is a")
    print("  notification - by the time it fires the money is gone, and")
    print("  people routinely mistake it for a cap.")

    print("\n  The strongest single control is `require_partition_filter`,")
    print("  because it turns the commonest expensive mistake - a forgotten")
    print("  WHERE clause - into an error at parse time rather than an")
    print("  invoice at month end.")

    print("\n  Capacity pricing is itself a cost control: a reservation is a")
    print("  ceiling on compute, so the bill is predictable even when a")
    print("  query is not. The trade is queueing instead of a surprise.")


def main() -> None:
    print("=" * 72)
    print("  BIGQUERY ECONOMICS - two crossovers".center(72))
    print("=" * 72)
    print("\n  Approximate US multi-region list prices. They move; the")
    print("  method does not.")

    c = compute_crossover()
    lt = long_term_storage()
    lp = logical_vs_physical()
    controls()

    banner("Summary - computed")
    print(f"  - 100 Enterprise slots cost ${c['monthly_slot_cost']:,.0f}/month, "
          f"idle or not")
    print(f"  - on-demand is cheaper below ~{c['crossover']:,.0f} TiB "
          f"scanned/month")
    print(f"  - a 3-year commitment moves that to "
          f"~{c['commitments']['3 years']['crossover']:,.0f} TiB")
    print(f"  - long-term storage is {1 - lt['long_term'] / lt['active']:.0%} "
          f"off, automatic - but only if you stop REWRITING the data")
    print(f"  - physical billing wins above "
          f"{PHYSICAL_ACTIVE / LOGICAL_ACTIVE:.1f}x compression, and "
          f"analytical data usually compresses 3-5x")
    print("\n  On-demand bills work done; capacity bills time reserved. Most")
    print("  of the wrong answers come from comparing them as if they were")
    print("  the same shape.")


if __name__ == "__main__":
    main()
