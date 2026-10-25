"""Which Cloud Storage class? It is a crossover, not a preference.

"Archive is cheapest" is the instinct and it is wrong whenever the data
is read. Colder classes trade a lower STORAGE price for a retrieval fee
and a minimum storage duration, so the right class depends entirely on
how often the data is actually touched - and on how long it will live.

  1. The four classes, and what each trades
  2. Total cost = storage + retrieval - computed
  3. The CROSSOVER: at what access frequency does each class win?
  4. The minimum-duration trap, which is the expensive one
  5. Lifecycle policies, and Autoclass

EXECUTED IN FULL. Pure arithmetic, no cloud, no dependencies.

** PRICES ARE APPROXIMATE ** and are list prices for a US multi-region
as of writing. They move, and they differ by region. The METHOD is the
point; re-check the numbers before quoting them at anyone.

Run:
    python 06_storage_decisions/01_object/storage_class_cost.py

Guide reference: Success Guide pp. 18-23; Ultimate Edition section 3.1.
"""

from __future__ import annotations

# (storage $/GB/month, retrieval $/GB, minimum storage duration in days)
CLASSES = {
    "Standard": (0.0260, 0.000, 0),
    "Nearline": (0.0100, 0.010, 30),
    "Coldline": (0.0040, 0.020, 90),
    "Archive":  (0.0012, 0.050, 365),
}

TB = 1024  # GB


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


def monthly_cost(cls: str, gb: float, reads_per_month: float) -> float:
    """Storage for a month, plus retrieving the whole object N times."""
    store, retrieve, _ = CLASSES[cls]
    return gb * store + gb * reads_per_month * retrieve


# ============================================ 1. the trade
def the_trade() -> None:
    banner("1. The four classes, and what each trades")

    print(f"  {'class':<10} {'$/GB/month':>12} {'$/GB retrieved':>16} "
          f"{'min duration':>14}")
    print("  " + "-" * 58)
    for name, (store, retrieve, mind) in CLASSES.items():
        mins = "none" if mind == 0 else f"{mind} days"
        print(f"  {name:<10} {store:>12.4f} {retrieve:>16.3f} {mins:>14}")

    cheapest = min(CLASSES, key=lambda c: CLASSES[c][0])
    ratio = CLASSES["Standard"][0] / CLASSES[cheapest][0]

    print(f"\n  Archive stores at {ratio:.0f}x less than Standard, which is")
    print("  why the instinct is to reach for it. But it charges")
    print(f"  ${CLASSES['Archive'][1]:.2f}/GB to read, where Standard charges")
    print("  nothing - so a single full read of an Archive object costs more")
    print("  than storing it in Standard for a year and a half.")

    print("\n  **The classes differ in DURABILITY not at all.** All four are")
    print("  the same eleven nines, the same API, the same latency to first")
    print("  byte. Only the price shape changes. Archive is not tape and")
    print("  there is no thaw - a common misconception carried over from")
    print("  other clouds.")


# ============================================ 2-3. the crossover
def crossover() -> dict:
    banner("2-3. Total cost by access frequency - 1 TB for one month")

    gb = TB
    rates = [0, 0.1, 0.25, 0.5, 1, 2, 4]

    header = f"  {'reads/month':>12} " + "".join(f"{c:>11}" for c in CLASSES)
    print(header)
    print("  " + "-" * (len(header) - 2))

    results = {}
    for r in rates:
        costs = {c: monthly_cost(c, gb, r) for c in CLASSES}
        best = min(costs, key=costs.get)
        results[r] = {"costs": costs, "best": best}
        row = f"  {r:>12.2f} "
        for c in CLASSES:
            mark = "*" if c == best else " "
            row += f"{'$' + format(costs[c], ',.2f') + mark:>11}"
        print(row)

    print("\n  * = cheapest at that access rate\n")

    # Where does each pair cross?
    print(f"  {'pair':<24} {'crosses at':>18}")
    print("  " + "-" * 46)
    pairs = [("Standard", "Nearline"), ("Nearline", "Coldline"),
             ("Coldline", "Archive")]
    crossings = {}
    for warm, cold in pairs:
        sw, rw, _ = CLASSES[warm]
        sc, rc, _ = CLASSES[cold]
        # gb*sw + gb*n*rw == gb*sc + gb*n*rc  ->  n = (sw - sc) / (rc - rw)
        n = (sw - sc) / (rc - rw)
        crossings[(warm, cold)] = n
        print(f"  {warm} vs {cold:<12} {n:>13.2f} reads/mo")

    print("\n  Read that as: **below the crossover the colder class wins;")
    print("  above it, the warmer one does.** Standard beats Nearline once")
    print(f"  you read the data more than {crossings[('Standard', 'Nearline')]:.1f} "
          f"times a month - which for")
    print("  anything a dashboard touches is every day.")

    print("\n  The mistake is reasoning about the storage price alone. A")
    print("  'cold' archive that a monthly report reads in full is not cold,")
    print("  and the retrieval fee quietly exceeds everything you saved.")
    return {"results": results, "crossings": crossings}


# ============================================ 4. minimum duration
def minimum_duration() -> dict:
    banner("4. The minimum-duration trap - the expensive one")

    gb = TB
    print(f"  Storing 1 TB, then deleting it after N days.\n")
    print(f"  {'deleted after':>14} " + "".join(f"{c:>11}" for c in CLASSES))
    print("  " + "-" * 60)

    out = {}
    for days in (1, 7, 30, 90, 365):
        row = f"  {str(days) + ' days':>14} "
        costs = {}
        for c, (store, _, mind) in CLASSES.items():
            billed_days = max(days, mind)          # <- the trap
            cost = gb * store * (billed_days / 30)
            costs[c] = cost
            row += f"{'$' + format(cost, ',.2f'):>11}"
        out[days] = costs
        print(row)

    one_day = out[1]
    print(f"\n  **Deleting after one day costs the same as keeping it for the")
    print("  minimum duration.** 1 TB in Archive for a single day bills")
    print(f"  ${one_day['Archive']:,.2f} - the full 365 days - while the same")
    print(f"  day in Standard costs ${one_day['Standard']:,.2f}.")

    print(f"\n  Note what that means: for short-lived data, Archive is "
          f"{one_day['Archive'] / one_day['Standard']:.0f}x")
    print("  MORE expensive than Standard, not cheaper. The early-deletion")
    print("  charge applies to overwriting and to class changes too, not")
    print("  only to deletes.")

    print("\n  This is the trap in an aggressive lifecycle policy: moving")
    print("  objects to Archive at 30 days and deleting them at 90 pays the")
    print("  full 365-day minimum on every object.")
    return out


# ============================================ 5. lifecycle
def lifecycle() -> None:
    banner("5. Lifecycle policies and Autoclass")

    print("  A lifecycle rule transitions or deletes objects by age, and it")
    print("  is the right tool when the ACCESS PATTERN IS PREDICTABLE:")
    print("      logs: Standard 30d -> Coldline 90d -> delete 400d")
    print("  Each hop must respect the minimum duration of the class it is")
    print("  leaving, or section 4 happens.")

    print("\n  **Autoclass moves objects between classes based on actual")
    print("  access**, with no minimum-duration charges on the transitions")
    print("  it makes. It costs a small management fee per object.")

    print("\n  The decision between them:")
    print("    predictable ageing, uniform objects  -> lifecycle rules")
    print("    unpredictable or mixed access        -> Autoclass")
    print("    many tiny objects                    -> watch the per-object")
    print("                                            Autoclass fee")

    print("\n  Two more things worth knowing for the exam:")
    print("    - object VERSIONING keeps noncurrent versions that are still")
    print("      billed; a lifecycle rule on noncurrent versions is how you")
    print("      stop paying for them forever")
    print("    - RETENTION POLICIES and holds BLOCK deletion, including by")
    print("      lifecycle rules. A locked retention policy cannot be")
    print("      shortened or removed by anyone, which is the point.")


def main() -> None:
    print("=" * 72)
    print("  CLOUD STORAGE CLASSES - a crossover, not a preference".center(72))
    print("=" * 72)
    print("\n  Prices are APPROXIMATE list prices for a US multi-region and")
    print("  move over time. The method is the point, not the digits.")

    the_trade()
    c = crossover()
    m = minimum_duration()
    lifecycle()

    banner("Summary - computed")
    sn = c["crossings"][("Standard", "Nearline")]
    print(f"  - Standard beats Nearline above {sn:.1f} reads/month")
    print(f"  - Nearline beats Coldline above "
          f"{c['crossings'][('Nearline', 'Coldline')]:.1f}")
    print(f"  - Coldline beats Archive above "
          f"{c['crossings'][('Coldline', 'Archive')]:.1f}")
    print(f"  - 1 TB deleted after ONE DAY: Archive "
          f"${m[1]['Archive']:,.2f} vs Standard ${m[1]['Standard']:,.2f} "
          f"- {m[1]['Archive'] / m[1]['Standard']:.0f}x worse")
    print("\n  Pick the class from how often the data is READ and how long it")
    print("  will LIVE. Storage price alone answers neither question.")


if __name__ == "__main__":
    main()
