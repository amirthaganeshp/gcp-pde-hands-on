"""De-identification: which transforms actually reduce risk, and which
only look like they do.

Sensitive Data Protection (formerly Cloud DLP) offers a menu of
de-identification transforms. They are not interchangeable, and the
exam tests whether you know what each one COSTS you - because the
choice is always a trade between three things you cannot have at once:

    can you get the original back?
    can you still JOIN on it?
    does it actually stop someone identifying a person?

The transforms themselves are ordinary algorithms, so they run here.
The DLP *service* - discovery, inspection, infoTypes - does not.

  1. The transforms, applied
  2. Reversible? Joinable? Format-preserving? - the trade table
  3. THE MEASUREMENT: hashing does not reduce re-identification risk
  4. Generalisation is the one that does - measured
  5. Date shifting, and why the offset must be per-entity

EXECUTED IN FULL. Pure Python over synthetic data.

Run:
    python 10_governance_security/01_sensitive_data/deidentification.py

Guide reference: Success Guide pp. 14-17; Ultimate Edition section 1.3.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import random
import string
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRIPS = REPO / "data" / "trips.csv"

# A demo key. A real one lives in Cloud KMS or Secret Manager and never
# appears in source - see section 6 of the README.
DEMO_KEY = b"demo-key-not-a-secret"

SEED = 42


def banner(text: str) -> None:
    print(f"\n{text}\n" + "-" * 72)


# ============================================ the transforms
def mask(value: str, keep: int = 4) -> str:
    """Replace all but the last `keep` characters."""
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * (len(value) - keep) + value[-keep:]


def redact(value: str) -> str:
    """Remove it entirely."""
    return ""


def pseudonymise(value: str) -> str:
    """Deterministic HMAC. Same input -> same output, keyed."""
    return hmac.new(DEMO_KEY, value.encode(), hashlib.sha256).hexdigest()[:16]


def fpe(value: str) -> str:
    """Format-preserving: same length, same character classes.

    A real FPE uses FF1/FF3 with a KMS-wrapped key. This is a keyed
    permutation per character class - enough to show the PROPERTY that
    matters, which is that the output still fits a column expecting the
    original shape.
    """
    out = []
    for i, ch in enumerate(value):
        h = int(hmac.new(DEMO_KEY, f"{i}{ch}".encode(),
                         hashlib.sha256).hexdigest(), 16)
        if ch.isdigit():
            out.append(string.digits[h % 10])
        elif ch.isalpha():
            alpha = string.ascii_uppercase if ch.isupper() else string.ascii_lowercase
            out.append(alpha[h % 26])
        else:
            out.append(ch)
    return "".join(out)


def bucketise(value: float, width: float = 10.0) -> str:
    """Generalisation: replace a value with the range it falls in."""
    lo = int(value // width) * width
    return f"[{lo:.0f}-{lo + width:.0f})"


def shift_date(iso: str, entity: str, max_days: int = 30) -> str:
    """Shift by a consistent offset PER ENTITY, so intervals survive."""
    h = int(hmac.new(DEMO_KEY, entity.encode(), hashlib.sha256).hexdigest(), 16)
    offset = (h % (2 * max_days)) - max_days
    dt = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
    return (dt + timedelta(days=offset)).isoformat()


# ============================================ 1-2. the trade
def the_transforms(rows: list[dict]) -> None:
    banner("1-2. The transforms, applied to the same value")

    sample = rows[0]["trip_id"]
    dur = float(rows[0]["duration_min"])

    print(f"  original trip_id : {sample}")
    print(f"  original duration: {dur:.2f} min\n")
    print(f"  {'transform':<22} {'result':<26}")
    print("  " + "-" * 52)
    print(f"  {'masking':<22} {mask(sample):<26}")
    print(f"  {'redaction':<22} {'(removed)':<26}")
    print(f"  {'pseudonymisation':<22} {pseudonymise(sample):<26}")
    print(f"  {'format-preserving':<22} {fpe(sample):<26}")
    print(f"  {'bucketing (duration)':<22} {bucketise(dur):<26}")

    banner("The trade - you cannot have all three")

    rows_t = [
        ("masking", "no", "no", "yes", "display only"),
        ("redaction", "no", "no", "n/a", "the column is gone"),
        ("pseudonymisation", "with a lookup", "YES", "no", "joins survive"),
        ("format-preserving", "with the key", "YES", "YES", "fits the column"),
        ("bucketing", "no", "partly", "no", "the only real risk cut"),
        ("date shifting", "with the key", "YES", "yes", "intervals survive"),
    ]
    print(f"  {'transform':<20} {'reversible':<14} {'joinable':<10} "
          f"{'same format':<12} note")
    print("  " + "-" * 74)
    for a, b, c, d, e in rows_t:
        print(f"  {a:<20} {b:<14} {c:<10} {d:<12} {e}")

    print("\n  **Reversible and joinable are different properties**, and")
    print("  confusing them is the common error. A hash is not reversible")
    print("  without a lookup table, but it IS joinable - and joinable is")
    print("  what lets someone link records back to a person.")


# ============================================ 3. the measurement
def hashing_does_not_help(rows: list[dict]) -> dict:
    banner("3. Hashing does NOT reduce re-identification risk - measured")

    ids = [r["trip_id"] for r in rows]

    original_unique = len(set(ids))
    hashed_unique = len(set(pseudonymise(i) for i in ids))
    fpe_unique = len(set(fpe(i) for i in ids))
    masked_unique = len(set(mask(i) for i in ids))

    print(f"  {len(ids):,} identifiers\n")
    print(f"  {'representation':<26} {'distinct values':>16} {'uniqueness':>12}")
    print("  " + "-" * 58)
    for label, n in (("original", original_unique),
                     ("pseudonymised (HMAC)", hashed_unique),
                     ("format-preserving", fpe_unique),
                     ("masked (last 4 kept)", masked_unique)):
        print(f"  {label:<26} {n:>16,} {n / len(ids):>11.1%}")

    print("\n  ** READ THE FPE ROW WITH CARE. ** The collisions there are a")
    print("  limitation of the TOY implementation in this file, which")
    print("  permutes each character position independently. A real FF1/FF3")
    print("  format-preserving encryption is a BIJECTION - it would preserve")
    print("  uniqueness at 100%, exactly like the HMAC row. The toy")
    print("  understates the risk, which is the wrong direction to be wrong")
    print("  in, so: assume real FPE behaves like pseudonymisation.")

    print("\n  **Pseudonymisation preserved uniqueness EXACTLY.** It has to -")
    print("  it is a function, so distinct inputs give distinct outputs.")
    print("  Every row is still individually distinguishable, still")
    print("  linkable across datasets, still trackable over time.")

    print("\n  That is the point people miss: 'we hashed the IDs, so it is")
    print("  anonymous' is **false**. It is PSEUDONYMISED - a different")
    print("  thing, still personal data under most regimes, and still")
    print("  re-identifiable by anyone holding the key, the lookup table,")
    print("  or enough context.")

    print("\n  Masking collapses uniqueness only because it destroys")
    print("  information - and with it, the column's usefulness.")
    return {"n": len(ids), "original": original_unique,
            "hashed": hashed_unique, "fpe": fpe_unique,
            "masked": masked_unique}


# ============================================ 4. generalisation
def generalisation(rows: list[dict]) -> dict:
    banner("4. Generalisation is the transform that actually reduces risk")

    def uniqueness(widths: float | None) -> tuple[int, int]:
        keys = []
        for r in rows:
            dur = float(r["duration_min"])
            d = f"{dur:.2f}" if widths is None else bucketise(dur, widths)
            keys.append((r["start_station"], r["bike_type"], d))
        c = Counter(keys)
        singles = sum(1 for v in c.values() if v == 1)
        return len(c), singles

    print(f"  Quasi-identifier: station + bike_type + duration\n")
    print(f"  {'duration held as':<26} {'groups':>9} {'groups of 1':>13} "
          f"{'at risk':>9}")
    print("  " + "-" * 62)

    out = {}
    exact_groups, exact_singles = uniqueness(None)
    print(f"  {'exact value':<26} {exact_groups:>9,} {exact_singles:>13,} "
          f"{exact_singles / exact_groups:>8.1%}")
    out["exact"] = (exact_groups, exact_singles)

    for w in (5, 10, 30):
        g, s = uniqueness(w)
        out[w] = (g, s)
        print(f"  {f'bucketed, width {w}':<26} {g:>9,} {s:>13,} "
              f"{s / g:>8.1%}")

    print("\n  **Bucketing is the only transform here that moves the")
    print("  re-identification number**, because it genuinely discards")
    print("  information - several people collapse into one group and")
    print("  become indistinguishable.")

    print("\n  That is also its cost, and it is the same trade as the")
    print("  aggregation threshold in 08_sharing_and_viz: you are buying")
    print("  privacy with resolution, and the analysis that needed the")
    print("  resolution no longer works.")

    print("\n  >> Masking and hashing protect a VALUE. Only generalisation")
    print("     protects a PERSON.")
    return out


# ============================================ 5. date shifting
def date_shifting(rows: list[dict]) -> dict:
    banner("5. Date shifting - the offset must be per entity")

    sample = [r for r in rows if r["start_station"] == rows[0]["start_station"]][:3]

    print("  Shifting every date by a PER-ENTITY offset:\n")
    print(f"  {'original':<28} {'shifted':<28}")
    print("  " + "-" * 58)
    for r in sample:
        shifted = shift_date(r["event_time"], r["start_station"])
        print(f"  {r['event_time'][:19]:<28} {shifted[:19]:<28}")

    # Intervals between two events for the SAME entity must survive.
    a, b = rows[0], rows[1]
    ent = "ST01"
    orig_gap = (datetime.fromisoformat(b["event_time"])
                - datetime.fromisoformat(a["event_time"])).total_seconds()
    new_gap = (datetime.fromisoformat(shift_date(b["event_time"], ent))
               - datetime.fromisoformat(shift_date(a["event_time"], ent))
               ).total_seconds()

    print(f"\n  interval between two events, same entity:")
    print(f"    before shifting : {orig_gap:>12,.0f} s")
    print(f"    after shifting  : {new_gap:>12,.0f} s")
    print(f"    preserved       : {orig_gap == new_gap}")

    print("\n  **A per-entity offset hides absolute dates while preserving")
    print("  intervals**, so 'how long between these two events' still")
    print("  works and 'when exactly did this happen' does not.")

    print("\n  Get this wrong in either direction and it fails:")
    print("    one offset for EVERYONE     - the whole dataset shifts")
    print("                                  together, so any known event")
    print("                                  reveals the offset and undoes it")
    print("    a NEW offset per ROW        - intervals are destroyed, and")
    print("                                  the data is useless for exactly")
    print("                                  the analysis it was kept for")
    return {"preserved": orig_gap == new_gap}


def main() -> None:
    if not TRIPS.exists():
        raise SystemExit(f"  {TRIPS} not found - run 00_setup/make_data.py first.")

    with TRIPS.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print("=" * 72)
    print("  DE-IDENTIFICATION - what each transform costs you".center(72))
    print("=" * 72)

    the_transforms(rows)
    h = hashing_does_not_help(rows)
    g = generalisation(rows)
    d = date_shifting(rows)

    banner("Summary - measured")
    print(f"  - pseudonymising {h['n']:,} ids preserved "
          f"{h['hashed'] / h['original']:.0%} of their uniqueness "
          f"- risk unchanged")
    print(f"  - exact durations: {g['exact'][1]:,} groups of one "
          f"({g['exact'][1] / g['exact'][0]:.0%} of groups)")
    print(f"  - bucketed to 30:  {g[30][1]:,} groups of one "
          f"({g[30][1] / g[30][0]:.0%})")
    print(f"  - date shifting preserved intervals: {d['preserved']}")
    print("\n  Hashing makes a value unreadable. It does not make a person")
    print("  unfindable. Only discarding information does that, and the")
    print("  information you discard is the analysis you lose.")


if __name__ == "__main__":
    main()
