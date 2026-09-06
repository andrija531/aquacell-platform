"""Read the year dataset and answer: what could the fleet have sold, and when?

Aggregates the 20 archetypes by population weight, in both directions:

  nadolje (shed)   = deferring heating we would otherwise have done
  nagore  (absorb) = taking energy on demand into an empty tank

Fleet figures are weighted per-device means scaled by fleet size. This assumes
errors across households are independent, which is true for draw timing and
false for season, holidays and network outages — so treat the fleet number as
an upper bound until correlated failure is modelled.

Run:  python3 -m aquacell_sim.analyse_year [fleet_size]
"""

from __future__ import annotations

import csv
import gzip
import json
import sys
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MONTH_NAMES = (
    "sij", "velj", "ozu", "tra", "svi", "lip",
    "srp", "kol", "ruj", "lis", "stu", "pro",
)


def load() -> tuple[dict, dict[str, dict[str, np.ndarray]]]:
    meta = json.loads((DATA_DIR / "metadata.json").read_text())
    weights = {a["id"]: a["weight"] for a in meta["archetypes"]}
    power = {a["id"]: a["power_w"] for a in meta["archetypes"]}

    cols: dict[str, dict[str, list]] = {}
    with gzip.open(DATA_DIR / "year_15min.csv.gz", "rt") as fh:
        for row in csv.DictReader(fh):
            if row["shed_available_wh"] == "":
                continue  # observer not live yet (first 30 days)
            store = cols.setdefault(
                row["archetype"],
                {"hour": [], "month": [], "shed": [], "absorb": [], "day_type": [],
                 "energy": [], "draw": [], "true": [], "lo": [], "hi": [],
                 "true_deficit_wh": []},
            )
            store["hour"].append(int(float(row["hour"])))
            store["month"].append(int(row["date"][5:7]))
            store["day_type"].append(row["day_type"])
            store["shed"].append(float(row["shed_available_wh"]))
            store["absorb"].append(float(row["absorb_available_wh"]))
            store["energy"].append(float(row["energy_in_wh"]))
            store["draw"].append(float(row["draw_wh"]))
            store["true"].append(float(row["true_stored_wh"]))
            store["lo"].append(float(row["d_lo_wh"]))
            store["hi"].append(float(row["d_hi_wh"]))
            store["true_deficit_wh"].append(
                float(row["true_deficit_wh"]) if row["true_deficit_wh"] else 0.0
            )

    data = {
        aid: {k: np.asarray(v) if k != "day_type" else np.asarray(v, dtype=object)
              for k, v in store.items()}
        for aid, store in cols.items()
    }
    return {"weights": weights, "power": power, "meta": meta}, data


def deliverable_power(info, data, aid: str) -> tuple[np.ndarray, np.ndarray]:
    """Convert energy budgets into power that could actually be measured.

    An energy budget is not a power offer. You can only *reduce* consumption
    that was going to happen anyway, and you can only *increase* it up to the
    element rating. Both directions are therefore capped by the baseline:

        nadolje = min(budget / block, baseline power)
        nagore  = min(budget / block, rating - baseline power)

    Ignoring this overstates shed capacity by roughly a factor of two, because
    a water heater is idle for most of the day.
    """
    d = data[aid]
    rating = info["power"][aid]
    block_h = 0.25
    baseline_w = d["energy"] / block_h  # Wh per 15 min -> W
    shed_w = np.minimum(d["shed"] / block_h, baseline_w)
    absorb_w = np.minimum(d["absorb"] / block_h, np.maximum(0.0, rating - baseline_w))
    return shed_w, absorb_w


def weighted_power_profile(info, data, key: str, n_bins: int) -> tuple[np.ndarray, np.ndarray]:
    shed = np.zeros(n_bins)
    absorb = np.zeros(n_bins)
    for aid, d in data.items():
        w = info["weights"][aid]
        shed_w, absorb_w = deliverable_power(info, data, aid)
        bins = d[key] - (1 if key == "month" else 0)
        for b in range(n_bins):
            mask = bins == b
            if mask.any():
                shed[b] += w * float(shed_w[mask].mean())
                absorb[b] += w * float(absorb_w[mask].mean())
    return shed, absorb


def weighted_profile(info, data, field: str, key: str, n_bins: int) -> np.ndarray:
    """Population-weighted mean of `field`, binned by `key`."""
    total = np.zeros(n_bins)
    for aid, d in data.items():
        w = info["weights"][aid]
        bins = d[key] - (1 if key == "month" else 0)
        for b in range(n_bins):
            mask = bins == b
            if mask.any():
                total[b] += w * float(d[field][mask].mean())
    return total


def main() -> None:
    fleet_size = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    info, data = load()

    print("=" * 78)
    print(f"FLOTA: {fleet_size} uredaja, tezinski agregat 20 arhetipova")
    print("=" * 78)

    shed_h, absorb_h = weighted_power_profile(info, data, "hour", 24)
    base_h = weighted_profile(info, data, "energy", "hour", 24) / 0.25
    print("\nPo satu dana. Prva tri stupca su PO JEDNOM UREDAJU, zadnja dva CIJELA FLOTA.")
    print(f"{'sat':>4} | {'baza':>8} {'dolje':>8} {'gore':>8} | "
          f"{'dolje':>10} {'gore':>10}")
    print(f"{'':>4} | {'W/ured':>8} {'W/ured':>8} {'W/ured':>8} | "
          f"{'MW flota':>10} {'MW flota':>10}")
    for h in range(24):
        print(
            f"{h:>4} | {base_h[h]:>8.0f} {shed_h[h]:>8.0f} {absorb_h[h]:>8.0f} | "
            f"{shed_h[h] * fleet_size / 1e6:>10.2f} "
            f"{absorb_h[h] * fleet_size / 1e6:>10.2f}"
        )

    shed_m, absorb_m = weighted_power_profile(info, data, "month", 12)
    print("\nPo mjesecu, snaga po uredaju (W):")
    print("   " + "".join(f"{m:>7s}" for m in MONTH_NAMES))
    print("   " + "".join(f"{shed_m[m]:>7.0f}" for m in range(12)) + "   nadolje")
    print("   " + "".join(f"{absorb_m[m]:>7.0f}" for m in range(12)) + "   nagore")

    print("\nPo arhetipu, cijela godina:")
    print(f"{'id':>4} {'tez.':>5} {'baza W':>7} {'dolje W':>8} {'gore W':>7} "
          f"{'pojas Wh':>9} {'sirina Wh':>10} {'kWh/god':>8}")
    for aid in sorted(data):
        d = data[aid]
        shed_w, absorb_w = deliverable_power(info, data, aid)
        print(
            f"{aid:>4} {info['weights'][aid]:>5.2f} "
            f"{d['energy'].mean() / 0.25:>7.0f} {shed_w.mean():>8.0f} "
            f"{absorb_w.mean():>7.0f} {d['shed'].mean():>9.0f} "
            f"{(d['hi'] - d['lo']).mean():>10.0f} {d['energy'].sum() / 1000:>8.0f}"
        )

    nameplate_kw = (
        sum(info["weights"][a] * info["power"][a] for a in data) * fleet_size / 1000
    )
    mean_shed_kw = float(np.mean(shed_h)) * fleet_size / 1000
    mean_absorb_kw = float(np.mean(absorb_h)) * fleet_size / 1000
    best_h = int(np.argmax(shed_h))
    worst_h = int(np.argmin(shed_h))
    print("\n" + "-" * 78)
    print(f"Nazivna snaga flote:        {nameplate_kw:8.0f} kW")
    print(f"Prosjecno nadolje:          {mean_shed_kw:8.0f} kW"
          f"   ({mean_shed_kw / nameplate_kw * 100:.1f} % nazivne)")
    print(f"Prosjecno nagore:           {mean_absorb_kw:8.0f} kW"
          f"   ({mean_absorb_kw / nameplate_kw * 100:.1f} % nazivne)")
    print(f"Najbolji sat nadolje: {best_h:2d}:00  "
          f"{shed_h[best_h] * fleet_size / 1000:.0f} kW")
    print(f"Najgori sat nadolje:  {worst_h:2d}:00  "
          f"{shed_h[worst_h] * fleet_size / 1000:.0f} kW")
    print(f"Za ponudu od 1 MW nadolje treba priblizno "
          f"{int(1000 / max(shed_h.min(), 1e-9) * 1000):d} uredaja "
          f"(prema najgorem satu)")
    print("-" * 78)
    print("\n" + info["meta"]["caveat"])


if __name__ == "__main__":
    main()
