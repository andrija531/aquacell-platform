"""Overview of all ten scenarios: physics, calibration, and baseline comfort.

Deliberately does no control at all beyond the weekly calibration night, so the
numbers describe the *tanks and households*, not any algorithm. This is the
reference every later result is measured against.

Run:  python3 -m aquacell_sim.run_scenarios
"""

from __future__ import annotations

import numpy as np

from .draws import generate
from .experiment import AlwaysClosed, CalibrationNight, run
from .scenarios import SCENARIOS, Scenario
from .tank import Environment

DAYS = 56
WH_PER_LITRE_KELVIN = 1.163


def season_env(scenario: Scenario, season: str) -> Environment:
    if season == "zima":
        return Environment(scenario.ambient_winter_c, t_inlet_c=8.0)
    return Environment(scenario.ambient_summer_c, t_inlet_c=18.0)


def analyse(scenario: Scenario, season: str) -> dict:
    env = season_env(scenario, season)
    spec = scenario.tank
    events = generate(scenario.household, DAYS, seed=1)
    litres_per_day = sum(e.volume_l for e in events) / DAYS

    base = run(scenario.household, DAYS, env, spec, seed=1, policy=AlwaysClosed())
    cal_run = run(
        scenario.household, DAYS, env, spec, seed=1,
        policy=CalibrationNight(defer_from_h=17.0),
    )
    cal = cal_run["calibration"]
    forced = sorted(
        r.energy_wh for r in cal_run["calibrator"].runs if r.forced and r.reached_cutout
    )

    theoretical = spec.total_capacity_wh_per_k * (60.0 - env.t_inlet_c)
    shower_wh = 40.0 * WH_PER_LITRE_KELVIN * (40.0 - env.t_inlet_c)

    return {
        "scenario": scenario,
        "season": season,
        "litres_per_day": litres_per_day,
        "theoretical_wh": theoretical,
        "shower_wh": shower_wh,
        "l_w": cal.l_w if cal else float("nan"),
        "e_hyst_wh": cal.e_hyst_quiet_wh if cal else float("nan"),
        "band_median_wh": float(np.median(forced)) if forced else float("nan"),
        "band_max_wh": forced[-1] if forced else float("nan"),
        "nights": len(forced),
        "base_failed": base["n_failed_showers"],
        "base_showers": base["n_showers"],
        "cal_failed": cal_run["n_failed_showers"],
        "cal_showers": cal_run["n_showers"],
    }


def main() -> None:
    for season in ("zima", "ljeto"):
        print("=" * 108)
        print(f"SEZONA: {season}     ({DAYS} dana po scenariju)")
        print("=" * 108)
        print(
            f"{'scenarij':18s} {'l/dan':>6s} {'teor.':>7s} {'tus':>6s} "
            f"{'L':>6s} {'E_hyst':>7s} {'pojas med':>10s} {'pojas max':>10s} "
            f"{'baza':>9s} {'kalib.noc':>10s}"
        )
        print("-" * 108)
        for scenario in SCENARIOS:
            r = analyse(scenario, season)
            print(
                f"{scenario.name:18s} {r['litres_per_day']:6.0f} "
                f"{r['theoretical_wh']:7.0f} {r['shower_wh']:6.0f} "
                f"{r['l_w']:6.1f} {r['e_hyst_wh']:7.0f} "
                f"{r['band_median_wh']:10.0f} {r['band_max_wh']:10.0f} "
                f"{r['base_failed']:4d}/{r['base_showers']:<4d} "
                f"{r['cal_failed']:4d}/{r['cal_showers']:<4d}"
            )
        print()
        print(
            "  teor. = teoretski kapacitet spremnika (Wh) | tus = energija jednog tusa (Wh)"
        )
        print(
            "  pojas = izmjereno dogrijavanje na kalibracijskim nocima (medijan / najdublje)"
        )
        print("  baza = pali tusevi bez ikakve kontrole | kalib.noc = s tjednom kalibracijom")


if __name__ == "__main__":
    main()
