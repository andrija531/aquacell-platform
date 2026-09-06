"""Capacity inside the windows when the grid actually needs each direction.

Capacity at 03:00 is worth little if nobody is buying at 03:00. The windows
below are where a Croatian TSO and the day-ahead market actually want each
direction:

  jutarnji vrh   06-09   upward regulation / peak shaving  -> needs REDUCTION
  vecernji vrh   17-21   the sharper of the two peaks       -> needs REDUCTION
  solarni visak  10-16   midday PV surplus, low or negative prices -> ABSORPTION
  nocni visak    00-05   low load, wind surplus             -> ABSORPTION

Split by half-year, because the evening peak matters most in winter and the
midday surplus most in summer.

Run:  python3 -m aquacell_sim.analyse_windows [fleet_size]
"""

from __future__ import annotations

import sys

import numpy as np

from .analyse_year import deliverable_power, load

WINDOWS = {
    "jutarnji vrh  06-09": (range(6, 10), "dolje"),
    "vecernji vrh  17-21": (range(17, 22), "dolje"),
    "solarni visak 10-16": (range(10, 17), "gore"),
    "nocni visak   00-05": (range(0, 6), "gore"),
}
HALF = {"listopad-mart": (10, 11, 12, 1, 2, 3), "april-septembar": (4, 5, 6, 7, 8, 9)}


def main() -> None:
    fleet = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    info, data = load()

    print("=" * 78)
    print(f"KAPACITET U TRZISNIM PROZORIMA, flota {fleet} uredaja")
    print("=" * 78)

    rows = []
    for label, (hours, direction) in WINDOWS.items():
        for season, months in HALF.items():
            per_device = 0.0
            p10 = 0.0
            for aid, d in data.items():
                w = info["weights"][aid]
                shed_w, absorb_w = deliverable_power(info, data, aid)
                series = shed_w if direction == "dolje" else absorb_w
                mask = np.isin(d["hour"], list(hours)) & np.isin(d["month"], list(months))
                if not mask.any():
                    continue
                per_device += w * float(series[mask].mean())
                p10 += w * float(np.percentile(series[mask], 10))
            rows.append((label, direction, season, per_device, p10))

    print(f"\n{'prozor':22s} {'smjer':6s} {'polugodiste':16s} "
          f"{'prosjek MW':>11s} {'p10 MW':>8s} {'uredaja/MW':>11s}")
    print("-" * 78)
    for label, direction, season, mean_w, p10_w in rows:
        mean_mw = mean_w * fleet / 1e6
        p10_mw = p10_w * fleet / 1e6
        need = int(1e6 / mean_w) if mean_w > 1 else 0
        print(
            f"{label:22s} {direction:6s} {season:16s} "
            f"{mean_mw:>11.2f} {p10_mw:>8.2f} {need:>11,d}"
        )

    print("\n" + "-" * 78)
    print("p10 = deseti percentil kroz sve blokove u tom prozoru, dakle vrijednost")
    print("koju prekoracis u 90 % slucajeva. To je blize onome sto se smije ponuditi")
    print("od prosjeka, ali jos ne uzima u obzir korelirane ispade.")
    print("uredaja/MW = koliko uredaja treba za 1 MW prema PROSJEKU tog prozora.")


if __name__ == "__main__":
    main()
