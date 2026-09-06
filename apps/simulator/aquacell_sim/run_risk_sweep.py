"""Risk sweep: what does a guarantee actually cost?

The first corrected run showed that a draw budget built on the 95th percentile
of hourly draw energy is not a worst case at all — a bath is far beyond it, so
the "guaranteed" bound is violated by construction. This sweeps the risk level
instead of pretending a guarantee is free, and reports the trade-off:

    higher quantile -> safer -> less shed time -> less revenue

Run:  python3 -m aquacell_sim.run_risk_sweep
"""

from __future__ import annotations

import numpy as np

from .draws import ALL_PROFILES, HouseholdProfile
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
QUANTILES = (0.90, 0.99, 0.999)
SEASONS = {
    "zima": Environment(t_ambient_c=22.0, t_inlet_c=8.0),
    "ljeto": Environment(t_ambient_c=26.0, t_inlet_c=18.0),
}


def analyse(profile: HouseholdProfile, env: Environment) -> dict:
    spec = TankSpec()
    train = run(profile, TRAIN_DAYS, env, spec, seed=1, policy=CalibrationNight())
    cal = train["calibration"]
    assert cal is not None
    hourly = hourly_draw_energy(train["trace"])

    base = run(profile, EVAL_DAYS, env, spec, seed=2, policy=AlwaysClosed())
    rows = []
    for q in QUANTILES:
        worst_case = make_worst_case_draw(draw_quantiles(hourly, q))
        shed = run(
            profile, EVAL_DAYS, env, spec, seed=2,
            policy=AggressiveShed(CalibrationNight()),
            calibration=cal, worst_case_draw_wh=worst_case,
        )
        a = shed["trace"].arrays()
        live = ~np.isnan(a["d_hi"]) & ~np.isnan(a["true_deficit_wh"])
        slack = a["d_hi"][live] - a["true_deficit_wh"][live]
        rows.append(
            {
                "q": q,
                "breach_pct": float(np.mean(slack < -1.0) * 100.0),
                "worst_breach_wh": float(max(0.0, -np.min(slack))),
                "shed_pct": shed["shed_fraction"] * 100.0,
                "failed": shed["n_failed_showers"],
                "showers": shed["n_showers"],
                "extra": shed["n_failed_showers"] - base["n_failed_showers"],
            }
        )
    return {
        "name": profile.name,
        "cal": cal,
        "base_failed": base["n_failed_showers"],
        "base_showers": base["n_showers"],
        "rows": rows,
        "theoretical_wh": float(
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
            print(
                f"  L {c.l_w:.0f} W | E_hyst {c.e_hyst_quiet_wh:.0f} Wh"
                f" | pojas {c.band_wh:.0f} Wh (p20, {c.n_calibration_nights} noci)"
                f" | manjak p95 {c.deficit_at_reclose_wh:.0f} Wh"
                f" | teoretski {r['theoretical_wh']:.0f} Wh"
            )
            print(
                f"  bazna razina bez kontrole: "
                f"{r['base_failed']}/{r['base_showers']} tuseva palo"
            )
            print("   kvantil | relej otvoren | prekrsaji | najgori | tusevi | dodatno")
            for row in r["rows"]:
                print(
                    f"    {row['q']:>6.3f} | {row['shed_pct']:>11.1f} % |"
                    f" {row['breach_pct']:>7.2f} % | {row['worst_breach_wh']:>5.0f} Wh |"
                    f" {row['failed']:>3d}/{row['showers']:<3d} |"
                    f" {row['extra']:>+4d}"
                )
    print("=" * 78)


if __name__ == "__main__":
    main()
