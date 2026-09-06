"""Synthesise a fleet from the archetypes and measure what it can actually bid.

The earlier window analysis summed each archetype's own 10th percentile, which
assumes every device in the fleet hits its worst case in the same second. That
is the opposite of true: a water heater's timing is nearly independent between
households, so the fleet sum is far steadier than any member of it. Summing
per-device worst cases produced a fleet p10 of zero, which is nonsense.

Here each synthetic device is an archetype drawn by population weight, plus a
whole-day time offset. The day offset decorrelates the draw pattern while
preserving hour of day and roughly preserving the season, which is exactly the
structure we want: independent timing, shared seasonality.

Run:  python3 -m aquacell_sim.analyse_fleet [fleet_size] [seed]
"""

from __future__ import annotations

import sys

import numpy as np

from .analyse_year import deliverable_power, load

BLOCKS_PER_DAY = 96
WINDOWS = {
    "jutarnji vrh  06-09": (range(6, 10), "dolje"),
    "vecernji vrh  17-21": (range(17, 22), "dolje"),
    "solarni visak 10-16": (range(10, 17), "gore"),
    "nocni visak   00-05": (range(0, 6), "gore"),
}
HALF = {"lis-mar": (10, 11, 12, 1, 2, 3), "apr-sep": (4, 5, 6, 7, 8, 9)}


def as_matrices(info, data):
    """Per archetype: [day, block] matrices of shed and absorb power, plus labels."""
    out = {}
    for aid, d in data.items():
        n = len(d["hour"])
        days = n // BLOCKS_PER_DAY
        if days < 2:
            continue
        cut = days * BLOCKS_PER_DAY
        shed_w, absorb_w = deliverable_power(info, data, aid)
        out[aid] = {
            "shed": shed_w[:cut].reshape(days, BLOCKS_PER_DAY),
            "absorb": absorb_w[:cut].reshape(days, BLOCKS_PER_DAY),
            "hour": d["hour"][:cut].reshape(days, BLOCKS_PER_DAY)[0],
            "month": d["month"][:cut].reshape(days, BLOCKS_PER_DAY)[:, 0],
        }
    return out


def build_fleet(info, mats, fleet_size: int, rng) -> dict[str, np.ndarray]:
    ids = list(mats)
    weights = np.array([info["weights"][a] for a in ids])
    weights = weights / weights.sum()
    days = min(m["shed"].shape[0] for m in mats.values())

    shed = np.zeros((days, BLOCKS_PER_DAY))
    absorb = np.zeros((days, BLOCKS_PER_DAY))
    picks = rng.choice(len(ids), size=fleet_size, p=weights)
    offsets = rng.integers(0, days, size=fleet_size)
    for pick, offset in zip(picks, offsets):
        m = mats[ids[pick]]
        shed += np.roll(m["shed"][:days], offset, axis=0)
        absorb += np.roll(m["absorb"][:days], offset, axis=0)
    return {"shed": shed, "absorb": absorb, "days": days}


def main() -> None:
    fleet_size = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    info, data = load()
    mats = as_matrices(info, data)
    rng = np.random.default_rng(seed)
    fleet = build_fleet(info, mats, fleet_size, rng)

    any_m = next(iter(mats.values()))
    hour_of_block = any_m["hour"].astype(int)
    days = fleet["days"]
    month_of_day = any_m["month"][:days].astype(int)

    print("=" * 82)
    print(f"SINTETSKA FLOTA: {fleet_size} uredaja, dan-offset po uredaju, seed {seed}")
    print("=" * 82)
    print(
        f"\n{'prozor':22s} {'smjer':6s} {'pol.':8s} {'prosjek':>9s} "
        f"{'p10':>8s} {'p1':>8s} {'min':>8s}  {'MW':>3s}"
    )
    print("-" * 82)
    for label, (hours, direction) in WINDOWS.items():
        series = fleet["shed"] if direction == "dolje" else fleet["absorb"]
        block_mask = np.isin(hour_of_block, list(hours))
        for season, months in HALF.items():
            day_mask = np.isin(month_of_day, list(months))
            vals = series[np.ix_(day_mask, block_mask)].ravel() / 1e6
            print(
                f"{label:22s} {direction:6s} {season:8s} {vals.mean():>9.2f} "
                f"{np.percentile(vals, 10):>8.2f} {np.percentile(vals, 1):>8.2f} "
                f"{vals.min():>8.2f}  MW"
            )

    print("\n" + "-" * 82)
    print("Za usporedbu, ista velicina flote na razlicitim brojevima uredaja")
    print("(pokazuje koliko se relativna nesigurnost smanjuje s velicinom flote):")
    print(f"\n{'uredaja':>8s} {'jutarnji vrh dolje':>22s} {'nocni visak gore':>20s}")
    for n in (100, 500, 1000, 5000, 20000):
        f = build_fleet(info, mats, n, np.random.default_rng(seed))
        out = []
        for label, (hours, direction) in (
            ("jutro", (range(6, 10), "dolje")),
            ("noc", (range(0, 6), "gore")),
        ):
            s = f["shed"] if direction == "dolje" else f["absorb"]
            bm = np.isin(hour_of_block, list(hours))
            v = s[:, bm].ravel()
            mean, p1 = v.mean(), np.percentile(v, 1)
            out.append(f"{mean / n:6.0f} W/ured, p1/prosjek {p1 / mean:4.2f}")
        print(f"{n:>8,d} {out[0]:>22s} {out[1]:>20s}")


if __name__ == "__main__":
    main()
