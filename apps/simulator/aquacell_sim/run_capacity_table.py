"""Four phases: calibrate, validate safety, measure comfort cost, report capacity.

Run:  python3 -m aquacell_sim.run_capacity_table
"""

from __future__ import annotations

import numpy as np

from .draws import ALL_PROFILES, HouseholdProfile
from .estimator import IntervalObserver
from .experiment import (
    AggressiveShed,
    AlwaysClosed,
    CalibrationNight,
    draw_quantiles,
    hourly_draw_energy,
    make_worst_case_draw,
    run,
)
from .tank import Environment, TankSpec

TRAIN_DAYS = 56
EVAL_DAYS = 56
SEASONS = {
    "zima": Environment(t_ambient_c=22.0, t_inlet_c=8.0),
    "ljeto": Environment(t_ambient_c=26.0, t_inlet_c=18.0),
}


def analyse(profile: HouseholdProfile, env: Environment) -> dict:
    spec = TankSpec()

    # -- Phase 1: uncontrolled + weekly calibration nights. Learn everything.
    train = run(profile, TRAIN_DAYS, env, spec, seed=1, policy=CalibrationNight())
    cal = train["calibration"]
    assert cal is not None, "calibration failed: too few complete cycles"

    p95 = draw_quantiles(hourly_draw_energy(train["trace"]), 0.95)
    worst_case = make_worst_case_draw(p95)

    # -- Phase 2: observer live, relay under the mechanical thermostat only.
    #    Validates the bound and gives the state the fleet would be in pre-bid.
    ev = run(
        profile, EVAL_DAYS, env, spec, seed=2, policy=CalibrationNight(),
        calibration=cal, worst_case_draw_wh=worst_case,
    )
    a = ev["trace"].arrays()
    live = ~np.isnan(a["d_hi"]) & ~np.isnan(a["true_deficit_wh"])
    slack = a["d_hi"][live] - a["true_deficit_wh"][live]
    breaches = int(np.sum(slack < -1.0))
    worst_breach = float(-np.min(slack)) if slack.size else 0.0

    # -- Phase 3: the same 56 days with an uncontrolled boiler, for the baseline.
    base = run(profile, EVAL_DAYS, env, spec, seed=2, policy=AlwaysClosed())

    # -- Phase 4: shed as hard as the observer allows. Measures the real cost.
    shed = run(
        profile, EVAL_DAYS, env, spec, seed=2,
        policy=AggressiveShed(CalibrationNight()),
        calibration=cal, worst_case_draw_wh=worst_case,
    )

    # capacity by hour, from the phase-2 state
    hours = (a["t_s"] // 3600).astype(int) % 24
    tmp = IntervalObserver(cal, worst_case)
    totals = np.zeros(24)
    counts = np.zeros(24)
    for idx in np.flatnonzero(live):
        tmp.d_lo, tmp.d_hi = a["d_lo"][idx], a["d_hi"][idx]
        totals[hours[idx]] += tmp.max_safe_shed_s(float(a["t_s"][idx]))
        counts[hours[idx]] += 1
    shed_by_hour_min = totals / np.maximum(counts, 1) / 60.0

    return {
        "name": profile.name,
        "cal": cal,
        "breaches": breaches,
        "worst_breach_wh": worst_breach,
        "mean_width_wh": float(np.mean(a["d_hi"][live] - a["d_lo"][live])),
        "base_failed": base["n_failed_showers"],
        "base_showers": base["n_showers"],
        "shed_failed": shed["n_failed_showers"],
        "shed_showers": shed["n_showers"],
        "shed_fraction": shed["shed_fraction"],
        "shed_by_hour_min": shed_by_hour_min,
        "theoretical_capacity_wh": float(
            spec.total_capacity_wh_per_k * (60.0 - env.t_inlet_c)
        ),
    }


def main() -> None:
    for season, env in SEASONS.items():
        for profile in ALL_PROFILES:
            r = analyse(profile, env)
            c = r["cal"]
            print("=" * 78)
            print(f"{r['name']}  /  {season}")
            print("-" * 78)
            print(f"  L                        {c.l_w:8.1f} W")
            print(f"  E_hyst (mirni ciklusi)   {c.e_hyst_quiet_wh:8.0f} Wh")
            print(f"  manjak pri uklopu (p95)  {c.deficit_at_reclose_wh:8.0f} Wh   <- sigurna granica")
            print(f"  prodajni pojas (p20)     {c.band_wh:8.0f} Wh   iz {c.n_calibration_nights} kalibracijskih noci")
            print(f"  teoretski kapacitet      {r['theoretical_capacity_wh']:8.0f} Wh")
            print(f"  srednja sirina pojasa    {r['mean_width_wh']:8.0f} Wh")
            print(
                f"  SIGURNOST                {r['breaches']:8d} prekrsaja"
                f"   (najgori {r['worst_breach_wh']:.0f} Wh)"
            )
            print(
                f"  KOMFOR   bez kontrole    {r['base_failed']:3d}/{r['base_showers']:3d}"
                f"   s kontrolom {r['shed_failed']:3d}/{r['shed_showers']:3d}"
                f"   -> dodatno {r['shed_failed'] - r['base_failed']:+d}"
            )
            print(f"  relej otvoren            {r['shed_fraction'] * 100:8.1f} % vremena")
            print("  zagarantirana redukcija, minute, po satu:")
            row = r["shed_by_hour_min"]
            for block in (0, 12):
                print("   " + "".join(f"{h:>5d}" for h in range(block, block + 12)))
                print("   " + "".join(f"{row[h]:>5.0f}" for h in range(block, block + 12)))
    print("=" * 78)


if __name__ == "__main__":
    main()
