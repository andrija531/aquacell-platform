"""How much is left on the table by bidding only what can be proven?

Compares three levels for the absorb direction:

  fizicki    what the tank could actually take (uses the ground truth)
  dokazivo   what the interval observer can guarantee (d_lo)
  statisticki  a fleet-level quantile of the physical capacity

The gap between the second and third is revenue currently being discarded,
because the market accepts a probabilistic offer with a penalty regime and does
not require a per-device guarantee.

Fleet variance is split into an independent part (draw timing, which averages
out as 1/sqrt(N)) and a correlated part (season, day type, holidays, which does
not). Only the correlated part justifies a margin.

Run:  python3 -m aquacell_sim.analyse_statistical [fleet_size]
"""

from __future__ import annotations

import sys

import numpy as np

from .analyse_year import load

BLOCK_H = 0.25


def main() -> None:
    fleet = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    info, data = load()

    hours = np.arange(24)
    phys = np.zeros(24)
    prov = np.zeros(24)
    indep_var = np.zeros(24)
    corr_var = np.zeros(24)

    for aid, d in data.items():
        w = info["weights"][aid]
        rating = info["power"][aid]
        baseline_w = d["energy"] / BLOCK_H
        headroom = np.maximum(0.0, rating - baseline_w)

        # physical: the true deficit is real room, whether or not we can prove it
        phys_w = np.minimum(d["true_deficit_wh"] / BLOCK_H, headroom)
        prov_w = np.minimum(d["lo"] / BLOCK_H, headroom)

        for h in hours:
            m = d["hour"] == h
            if not m.any():
                continue
            phys[h] += w * float(phys_w[m].mean())
            prov[h] += w * float(prov_w[m].mean())
            # variance within an (archetype, hour) cell is draw timing:
            # independent across households, so it averages out
            indep_var[h] += (w**2) * float(phys_w[m].var())

    # correlated variance: how much the *daily mean* of the whole fleet moves
    # from day to day. This does not average out with fleet size.
    daily = {}
    for aid, d in data.items():
        w = info["weights"][aid]
        rating = info["power"][aid]
        baseline_w = d["energy"] / BLOCK_H
        phys_w = np.minimum(
            d["true_deficit_wh"] / BLOCK_H, np.maximum(0.0, rating - baseline_w)
        )
        day_id = (d["month"] * 100).astype(int)  # coarse: month as the correlated unit
        for h in hours:
            m = d["hour"] == h
            for u in np.unique(day_id[m]):
                key = (h, int(u))
                daily.setdefault(key, 0.0)
                sel = m & (day_id == u)
                daily[key] += w * float(phys_w[sel].mean())
    for h in hours:
        vals = [v for (hh, _), v in daily.items() if hh == h]
        corr_var[h] = float(np.var(vals)) if len(vals) > 1 else 0.0

    print("=" * 78)
    print(f"APSORPCIJA: dokazivo vs statisticki, flota {fleet} uredaja")
    print("=" * 78)
    print(
        f"{'sat':>4} | {'fizicki':>8} {'dokazivo':>9} {'propusteno':>11} | "
        f"{'ponuda p95':>11} {'flota MW':>9}"
    )
    print(f"{'':>4} | {'W/ured':>8} {'W/ured':>9} {'faktor':>11} | "
          f"{'W/ured':>11} {'p95':>9}")
    total_prov = total_bid = 0.0
    for h in hours:
        sigma_fleet = np.sqrt(indep_var[h] / fleet + corr_var[h])
        bid = max(0.0, phys[h] - 1.645 * sigma_fleet)  # one-sided 95 %
        factor = phys[h] / prov[h] if prov[h] > 1e-9 else float("inf")
        total_prov += prov[h]
        total_bid += bid
        print(
            f"{h:>4} | {phys[h]:>8.0f} {prov[h]:>9.0f} {factor:>11.1f}x | "
            f"{bid:>11.0f} {bid * fleet / 1e6:>9.2f}"
        )

    print("-" * 78)
    print(f"Prosjek dokazivo:   {total_prov / 24:7.0f} W/ured"
          f"   = {total_prov / 24 * fleet / 1e6:5.2f} MW")
    print(f"Prosjek ponuda p95: {total_bid / 24:7.0f} W/ured"
          f"   = {total_bid / 24 * fleet / 1e6:5.2f} MW")
    print(f"Dobitak:            {total_bid / max(total_prov, 1e-9):7.1f}x")
    print("-" * 78)
    print(
        "\nponuda p95 = fizicki prosjek minus 1,645 sigma flote, gdje sigma sadrzi\n"
        "nezavisni dio podijeljen s korijenom iz broja uredaja plus korelirani dio\n"
        "u cijelosti. Znaci: u 5 % blokova ne bi dostavio sve, i za to placas kaznu."
    )


if __name__ == "__main__":
    main()
