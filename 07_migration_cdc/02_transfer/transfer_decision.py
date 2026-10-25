"""Online or appliance? The arithmetic the exam is really testing.

"We have 500 TB to move" questions have one correct method and it is
division. People get this wrong by orders of magnitude because they
reason from the size alone - but the size is only half of it, and the
nominal link speed is not the speed you get.

  1. How long does N terabytes take over a link?
  2. Nominal vs EFFECTIVE bandwidth - the factor people forget
  3. The crossover: where Transfer Appliance starts to win
  4. The decision table, computed rather than asserted
  5. Which service, once the method is chosen

EXECUTED IN FULL. Pure arithmetic, no dependencies, no cloud.

Run:
    python 07_migration_cdc/02_transfer/transfer_decision.py

Guide reference: Success Guide pp. 21-22; Ultimate Edition section 2.1.
"""

from __future__ import annotations

# Real links rarely deliver their nominal rate for a sustained bulk
# transfer: TCP behaviour over long distances, shared use, and the fact
# that the link also carries the business. 70% is a common planning
# figure and is generous for a link that is not dedicated.
EFFICIENCY = 0.70

# Transfer Appliance is not instant either. Request, ship, load on site,
# ship back, ingest at Google. Two to three weeks door to door is a fair
# planning figure; this uses the optimistic end.
APPLIANCE_DAYS = 14

LINKS = [
    ("100 Mbps", 100e6),
    ("500 Mbps", 500e6),
    ("1 Gbps", 1e9),
    ("10 Gbps", 10e9),
]

SIZES_TB = [1, 10, 100, 500, 1000]


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


def days_for(tb: float, bits_per_sec: float, efficiency: float) -> float:
    bytes_total = tb * 1e12
    effective_bytes_per_sec = (bits_per_sec * efficiency) / 8
    return bytes_total / effective_bytes_per_sec / 86400


def fmt_days(d: float) -> str:
    if d < 1:
        return f"{d * 24:.1f} h"
    if d < 365:
        return f"{d:.0f} d"
    return f"{d / 365:.1f} yr"


# ============================================ 1-2. the arithmetic
def the_arithmetic() -> None:
    banner("1-2. Nominal vs effective bandwidth")

    tb = 100
    print(f"  Moving {tb} TB over a 1 Gbps link.\n")
    nominal = days_for(tb, 1e9, 1.0)
    effective = days_for(tb, 1e9, EFFICIENCY)

    print(f"  at 100% of nominal      : {fmt_days(nominal)}")
    print(f"  at {EFFICIENCY:.0%} (planning figure) : {fmt_days(effective)}")
    print(f"  difference              : {effective - nominal:.1f} days")

    print("\n  **A link does not deliver its nameplate rate for a sustained")
    print("  bulk transfer.** TCP over distance, shared use, and the fact")
    print("  that the link still has to carry the business. 70% is a common")
    print("  planning figure and is generous for a link that is not")
    print("  dedicated to the migration.")

    print("\n  The arithmetic itself is just:")
    print("      days = bytes / (bits_per_sec x efficiency / 8) / 86400")
    print("  and the exam question is always whether the answer is bigger")
    print("  or smaller than the appliance turnaround.")


# ============================================ 3-4. the matrix
def the_matrix() -> dict:
    banner("3-4. Time to transfer, and where the appliance wins")

    print(f"  Effective bandwidth = {EFFICIENCY:.0%} of nominal. "
          f"Transfer Appliance assumed {APPLIANCE_DAYS} days door to door.\n")

    header = f"  {'size':>8} " + "".join(f"{name:>12}" for name, _ in LINKS)
    print(header)
    print("  " + "-" * (len(header) - 2))

    results = {}
    for tb in SIZES_TB:
        row = f"  {tb:>6} TB "
        for name, bps in LINKS:
            d = days_for(tb, bps, EFFICIENCY)
            mark = "*" if d > APPLIANCE_DAYS else " "
            row += f"{fmt_days(d) + mark:>12}"
            results[(tb, name)] = d
        print(row)

    print(f"\n  * = slower than shipping an appliance "
          f"({APPLIANCE_DAYS} days)")

    slow = results[(100, "100 Mbps")]
    fast = results[(100, "10 Gbps")]
    huge = results[(1000, "100 Mbps")]

    print(f"\n  Read the 100 Mbps column. **100 TB takes "
          f"{fmt_days(slow)}**, and 1 PB")
    print(f"  takes {fmt_days(huge)}. That is not a slow migration, it is an")
    print("  impossible one - and it is the shape of question the exam asks,")
    print("  because the instinct is to reason about the size and not the")
    print("  link.")

    print(f"\n  Now read the 10 Gbps column. The same 100 TB takes "
          f"{fmt_days(fast)} -")
    print(f"  **{slow / fast:.0f}x faster, for the same data.** The size alone "
          f"never")
    print("  decides it.")
    return results


def crossovers() -> dict:
    banner("Where exactly does the appliance start to win?")

    print(f"  The size at which an online transfer takes longer than the")
    print(f"  {APPLIANCE_DAYS}-day appliance turnaround:\n")
    print(f"  {'link':>10}   {'crossover':>12}")
    print("  " + "-" * 28)

    out = {}
    for name, bps in LINKS:
        tb = (bps * EFFICIENCY / 8) * APPLIANCE_DAYS * 86400 / 1e12
        out[name] = tb
        print(f"  {name:>10}   {tb:>9.1f} TB")

    print("\n  Below the crossover, transfer online - shipping hardware for")
    print("  a few terabytes is slower and more work. Above it, the")
    print("  appliance wins however inconvenient it feels.")
    print("\n  Two adjustments that move these numbers in practice:")
    print("    - a DEDICATED link during a migration window raises the")
    print("      efficiency figure and moves the crossover right")
    print("    - Cloud Interconnect changes the question entirely, and is")
    print("      the answer when the transfer is ongoing rather than once")
    return out


# ============================================ 5. which service
def which_service() -> None:
    banner("5. Which service, once the method is chosen")

    rows = [
        ("cloud to GCS, ongoing or scheduled", "Storage Transfer Service"),
        ("S3 or Azure Blob to GCS", "Storage Transfer Service"),
        ("on-prem to GCS over the network", "Storage Transfer Service (agent)"),
        ("on-prem, too big for the link", "Transfer Appliance"),
        ("a few files, interactively", "gcloud storage cp"),
        ("SaaS into BigQuery on a schedule", "BigQuery Data Transfer Service"),
        ("a live database, minimal downtime", "Database Migration Service"),
        ("a live database, stream the changes", "Datastream"),
    ]
    print(f"  {'situation':<42} service")
    print("  " + "-" * 72)
    for a, b in rows:
        print(f"  {a:<42} {b}")

    print("\n  **Storage Transfer Service is for FILES; DMS and Datastream")
    print("  are for DATABASES.** Confusing the two is the commonest wrong")
    print("  answer, and the giveaway word in the question is whether the")
    print("  source is a bucket or an engine.")

    print("\n  DMS vs Datastream, since both touch live databases:")
    print("    DMS         MIGRATE and cut over. The goal is to stop using")
    print("                the source. Handles schema conversion.")
    print("    Datastream  REPLICATE continuously. The source keeps running")
    print("                and you want its changes elsewhere - which is")
    print("                the CDC stream in 01_datastream.")

    print("\n  A migration with minimal downtime is both patterns at once:")
    print("  bulk load, then CDC to catch up, then cut over when the lag")
    print("  is small enough - the four phases in the section README.")


def main() -> None:
    print("=" * 72)
    print("  TRANSFER: ONLINE OR APPLIANCE?".center(72))
    print("=" * 72)

    the_arithmetic()
    m = the_matrix()
    c = crossovers()
    which_service()

    banner("Summary - computed, not asserted")
    print(f"  - 100 TB at 100 Mbps : {fmt_days(m[(100, '100 Mbps')])}")
    print(f"  - 100 TB at 10 Gbps  : {fmt_days(m[(100, '10 Gbps')])}  "
          f"<- same data, {m[(100, '100 Mbps')] / m[(100, '10 Gbps')]:.0f}x faster")
    print(f"  - 1 PB  at 100 Mbps  : {fmt_days(m[(1000, '100 Mbps')])}  "
          f"<- not slow, impossible")
    print(f"  - crossover at 1 Gbps: {c['1 Gbps']:.0f} TB")
    print("\n  The question is never 'how much data'. It is 'how much data")
    print("  divided by how fast a link, against how long a van takes'.")


if __name__ == "__main__":
    main()
