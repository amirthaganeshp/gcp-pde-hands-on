"""Sharing data safely: why clean rooms have an aggregation threshold.

Analytics Hub shares datasets. Data clean rooms share ANALYSIS without
sharing rows - two parties join their data, neither sees the other's
records, and only aggregates come out. The mechanism that makes that
safe is an AGGREGATION THRESHOLD, and this file measures why it is not
optional.

  1. The sharing ladder - what each mechanism actually exposes
  2. Small groups leak identity - measured
  3. The aggregation threshold, and what it costs you
  4. Differencing: why one query is safe and two are not
  5. Analytics Hub vs authorised views vs clean rooms

EXECUTED IN FULL. Pure Python over the trip data.

Run:
    python 00_setup/make_data.py       # once
    python 08_sharing_and_viz/01_sharing/sharing_privacy.py

Guide reference: Success Guide pp. 16, 45; Ultimate Edition section 4.3.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRIPS = REPO / "data" / "trips.csv"

K = 5            # the usual minimum group size


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


def load() -> list[dict]:
    with TRIPS.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ============================================ 1. the ladder
def the_ladder() -> None:
    banner("1. The sharing ladder - what each mechanism exposes")

    rows = [
        ("copy the table", "everything, forever", "no control after the copy"),
        ("grant dataset access", "every row, live", "they see what you see"),
        ("authorised view", "the rows the view selects", "you choose the slice"),
        ("Analytics Hub listing", "a live linked dataset", "revocable, usage visible"),
        ("data clean room", "AGGREGATES ONLY", "neither side sees rows"),
    ]
    print(f"  {'mechanism':<24} {'consumer sees':<28} note")
    print("  " + "-" * 74)
    for a, b, c in rows:
        print(f"  {a:<24} {b:<28} {c}")

    print("\n  **Copying is the one to avoid.** The moment data leaves as a")
    print("  copy you lose revocation, you lose freshness, and you lose any")
    print("  record of who has what. Every mechanism below it exists to")
    print("  avoid making a copy.")

    print("\n  Analytics Hub shares a LINKED DATASET - the consumer queries")
    print("  your data in place, pays for their own compute, and you can")
    print("  revoke it. No egress, no duplicate, no staleness.")


# ============================================ 2. small groups leak
def dims_for(t: dict, n: int) -> tuple:
    """The first n quasi-identifiers of a trip."""
    hour = t["event_time"][11:13]
    bucket = str(int(float(t["duration_min"]) // 5) * 5)
    all_dims = (t["start_station"], t["bike_type"], t["member"],
                t["end_station"], hour, bucket)
    return all_dims[:n]


def small_groups(trips: list[dict]) -> dict:
    banner("2. Every extra dimension cuts the groups smaller - measured")

    names = ["station", "bike_type", "member", "end_station",
             "hour", "duration_bucket"]

    print(f"  COUNT(*) grouped by an increasing set of quasi-identifiers,")
    print(f"  over the same {len(trips):,} trips.\n")
    print(f"  {'dimensions (cumulative)':<26} {'groups':>8} {'smallest':>9} "
          f"{'size 1':>8} {f'< k={K}':>8}")
    print("  " + "-" * 64)

    rows = []
    for n in range(1, 7):
        g: Counter = Counter(dims_for(t, n) for t in trips)
        sizes = sorted(g.values())
        singles = sum(1 for v in g.values() if v == 1)
        under = sum(1 for v in g.values() if v < K)
        label = f"{n}: +{names[n - 1]}" if n > 1 else "1: station"
        rows.append({"n": n, "groups": len(g), "smallest": sizes[0],
                     "singletons": singles, "under_k": under})
        print(f"  {label:<26} {len(g):>8,} {sizes[0]:>9,} "
              f"{singles:>8,} {under:>8,}")

    first_leak = next((r for r in rows if r["singletons"] > 0), None)
    final = rows[-1]

    print(f"\n  **A group of one IS a row.** 'A 20-25 minute cargo-bike trip")
    print("  from Old Docks to Campus West at 06:00 by a non-member'")
    print("  identifies a person as surely as publishing their name. The")
    print("  aggregate is a disguise, not a protection.")

    if first_leak:
        print(f"\n  Singletons appear at **{first_leak['n']} dimensions** "
              f"({first_leak['singletons']:,} of them),")
        print(f"  and by {final['n']} there are {final['singletons']:,} - "
              f"{final['singletons'] / final['groups']:.0%} of all groups.")

    print("\n  This is why 'we only publish aggregates' is not a privacy")
    print("  control by itself. Nobody adds a dangerous column; they add a")
    print("  useful one, and the groups get smaller each time.")
    return {"rows": rows, "final": final,
            "first_leak": first_leak["n"] if first_leak else None}


# ============================================ 3. the threshold
def threshold(trips: list[dict], s: dict) -> dict:
    banner(f"3. The aggregation threshold (k={K}) and what it costs")

    # Use the full quasi-identifier set from section 2 - that is where
    # the small groups actually are.
    groups: Counter = Counter(dims_for(t, 6) for t in trips)

    print(f"  {'k':>3} {'groups kept':>13} {'groups hidden':>15} "
          f"{'trips kept':>12} {'% of trips':>12}")
    print("  " + "-" * 62)

    out = {}
    total = sum(groups.values())
    for k in (1, 3, 5, 10, 50):
        kept = {g: v for g, v in groups.items() if v >= k}
        kept_rows = sum(kept.values())
        out[k] = {"groups": len(kept), "rows": kept_rows}
        print(f"  {k:>3} {len(kept):>13,} {len(groups) - len(kept):>15,} "
              f"{kept_rows:>12,} {kept_rows / total:>11.1%}")

    print(f"\n  **The threshold is a privacy/utility dial, and it is not")
    print("  free.** At k=5 the small groups vanish, and with them a slice")
    print("  of legitimate analysis - the rare combinations are often the")
    print("  interesting ones.")

    print("\n  BigQuery clean rooms enforce this with an ANALYSIS RULE:")
    print("      aggregation_threshold_policy - minimum group size, and")
    print("      which columns must be aggregated")
    print("  The consumer cannot disable it, and a query that would return")
    print("  a smaller group returns nothing rather than a small number.")
    print("  That distinction matters: an error would itself leak.")
    return out


# ============================================ 4. differencing
def differencing(trips: list[dict]) -> dict:
    banner("4. Differencing - why one safe query plus one safe query is not")

    station = "ST01"
    a = sum(1 for t in trips if t["start_station"] == station)
    b = sum(1 for t in trips
            if t["start_station"] == station and t["bike_type"] != "cargo")
    diff = a - b

    print(f"  query 1: trips from {station}                  -> {a:>6,}")
    print(f"  query 2: trips from {station}, excluding cargo -> {b:>6,}")
    print(f"  the difference                                 -> {diff:>6,}")

    print(f"\n  Both queries clear any sensible threshold - {a:,} and {b:,}")
    print(f"  are large groups. Their DIFFERENCE is {diff:,}, and that")
    print("  number was never aggregated, never thresholded, and never")
    print("  reviewed.")

    print("\n  **Thresholds protect a query, not a questioner.** Two")
    print("  permitted queries can isolate a group far smaller than either,")
    print("  and repeated with narrower filters this converges on a single")
    print("  row.")

    print("\n  That is why clean rooms also constrain the JOIN KEYS and the")
    print("  columns available, and why query logs are visible to the")
    print("  publisher. The threshold is necessary and nowhere near")
    print("  sufficient on its own.")
    return {"a": a, "b": b, "diff": diff}


# ============================================ 5. which mechanism
def which_mechanism() -> None:
    banner("5. Which sharing mechanism")

    rows = [
        ("another team, same org, live data", "authorised view / dataset IAM"),
        ("a partner org, ongoing, revocable", "Analytics Hub listing"),
        ("a marketplace of internal datasets", "Analytics Hub"),
        ("two parties joining data, neither trusts", "data clean room"),
        ("hide columns, not rows", "policy tags / column-level security"),
        ("hide rows by who is asking", "row-level access policies"),
        ("an external system that must own a copy", "scheduled export - last resort"),
    ]
    print(f"  {'situation':<42} mechanism")
    print("  " + "-" * 74)
    for a, b in rows:
        print(f"  {a:<42} {b}")

    print("\n  **Analytics Hub is the default answer for cross-organisation")
    print("  sharing on the exam.** Linked datasets are live, revocable, and")
    print("  the consumer pays their own query costs - which is usually the")
    print("  detail the question is pointing at.")

    print("\n  Authorised views vs clean rooms is the other common pair:")
    print("    authorised view  YOU decide the slice, they see those rows")
    print("    clean room       NOBODY sees rows, only aggregates")


def main() -> None:
    if not TRIPS.exists():
        raise SystemExit(f"  {TRIPS} not found - run 00_setup/make_data.py first.")

    print("=" * 72)
    print("  SHARING DATA SAFELY".center(72))
    print("=" * 72)

    trips = load()
    the_ladder()
    s = small_groups(trips)
    t = threshold(trips, s)
    d = differencing(trips)
    which_mechanism()

    banner("Summary - measured")
    f = s["final"]
    print(f"  - at {f['n']} dimensions: {f['groups']:,} groups, "
          f"{f['singletons']:,} of size 1 - each of those is a person")
    print(f"  - at k={K}: {t[K]['groups']:,} groups survive, "
          f"{t[K]['rows']:,} trips ({t[K]['rows'] / len(trips):.1%})")
    print(f"  - differencing two PERMITTED queries isolated a group of "
          f"{d['diff']:,}")
    print("\n  Aggregation is not anonymisation. A threshold makes a single")
    print("  query safe; it does not make a questioner safe.")


if __name__ == "__main__":
    main()
