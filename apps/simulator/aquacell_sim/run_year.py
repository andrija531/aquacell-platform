"""Simulate a full year for all archetypes and write the dataset to disk.

Outputs (into apps/simulator/data/):

  metadata.json        archetype definitions, weights, assumptions, schema
  year_15min.csv.gz    one row per archetype per 15 minutes  (the main dataset)
  year_events.csv.gz   every thermostat transition, full resolution
  year_summary.csv     one row per archetype, headline figures

Run:  python3 -m aquacell_sim.run_year            (all 20, ~15-25 min)
      python3 -m aquacell_sim.run_year A01 A07    (subset)
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

from .archetypes import ARCHETYPES, WEIGHT_SOURCE, Archetype
from .calendar_hr import build_year, public_holidays
from .year import ROW_FIELDS, generate_year, simulate_year

YEAR = 2025
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COLLECT_ONLY_DAYS = 30

CAVEAT = (
    "Sintetski podaci. Fizika spremnika je standardna termodinamika i provjerena "
    "je protiv neovisnog rucnog izracuna. Ponasanje korisnika (volumen tusa, broj "
    "tuseva, oblik dnevne krivulje, praznici, rad od doma) je PROCJENA, nije "
    "mjereno na hrvatskim domacinstvima. Isto vrijedi za tezine arhetipova i za "
    "polozaj sonde termostata, koji je podesen da reproducira ocekivano trajanje "
    "grijanja. Oblik i relativni odnosi medju arhetipovima su vjerodostojni; "
    "apsolutne brojke nisu i ne smiju same uci u financijski model."
)


def stable_seed(text: str) -> int:
    """Python's hash() is randomised per process, which made runs irreproducible."""
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big")


def run_one(archetype: Archetype, year: int = YEAR) -> dict:
    rng = np.random.default_rng(stable_seed(archetype.id))
    days = build_year(
        year, rng,
        wfh_days_per_week=archetype.wfh_days_per_week,
        annual_leave_weeks=archetype.annual_leave_weeks,
        winter_break_days=archetype.winter_break_days,
        weekend_only=archetype.weekend_only,
    )
    events = generate_year(
        archetype.household, days, rng, has_children=archetype.has_children
    )
    result = simulate_year(
        archetype.household, days, events, archetype.spec,
        unheated=archetype.unheated, collect_only_days=COLLECT_ONLY_DAYS,
    )

    showers = [o for o in result.outcomes if o.is_shower]
    failed = [o for o in showers if o.failed]
    cal = result.calibration
    away_days = sum(1 for d in days if d.day_type.value == "odsutni")

    rows = result.rows
    shed = np.array(
        [float(r[ROW_FIELDS.index("shed_available_wh")] or 0.0) for r in rows]
    )
    absorb = np.array(
        [float(r[ROW_FIELDS.index("absorb_available_wh")] or 0.0) for r in rows]
    )
    energy = np.array([float(r[ROW_FIELDS.index("energy_in_wh")]) for r in rows])

    return {
        "archetype": archetype,
        "rows": rows,
        "events": result.events,
        "summary": {
            "id": archetype.id,
            "note": archetype.note,
            "weight": archetype.weight,
            "volume_l": archetype.spec.volume_l,
            "power_w": archetype.spec.element_power_w,
            "occupants": archetype.household.occupants,
            "unheated": int(archetype.unheated),
            "needs_contactor": int(archetype.needs_contactor),
            "away_days": away_days,
            "litres_per_day": round(result.litres_per_day, 1),
            "kwh_per_year": round(float(energy.sum()) / 1000.0, 1),
            "l_w": round(cal.l_w, 2) if cal else "",
            "e_hyst_wh": round(cal.e_hyst_quiet_wh, 0) if cal else "",
            "band_wh": round(cal.band_wh, 0) if cal else "",
            "deficit_p95_wh": round(cal.deficit_at_reclose_wh, 0) if cal else "",
            "calibration_nights": cal.n_calibration_nights if cal else 0,
            "showers": len(showers),
            "failed_showers": len(failed),
            "failed_pct": round(100.0 * len(failed) / max(1, len(showers)), 2),
            "mean_shed_wh": round(float(shed.mean()), 0),
            "mean_absorb_wh": round(float(absorb.mean()), 0),
            "shed_p90_wh": round(float(np.percentile(shed, 90)), 0),
            "absorb_p90_wh": round(float(np.percentile(absorb, 90)), 0),
        },
    }


def main() -> None:
    wanted = sys.argv[1:]
    selected = [a for a in ARCHETYPES if not wanted or a.id in wanted]
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    summaries = []
    t0 = time.time()
    with gzip.open(DATA_DIR / "year_15min.csv.gz", "wt", newline="") as fh, gzip.open(
        DATA_DIR / "year_events.csv.gz", "wt", newline=""
    ) as eh:
        writer = csv.writer(fh)
        writer.writerow(("archetype",) + ROW_FIELDS)
        ewriter = csv.writer(eh)
        ewriter.writerow(("archetype", "t_s", "date", "event", "top_temp_c"))

        for i, archetype in enumerate(selected, 1):
            started = time.time()
            out = run_one(archetype)
            for row in out["rows"]:
                writer.writerow((archetype.id,) + row)
            for ev in out["events"]:
                ewriter.writerow((archetype.id,) + ev)
            summaries.append(out["summary"])
            s = out["summary"]
            print(
                f"[{i:2d}/{len(selected)}] {archetype.id} {archetype.note[:42]:42s}"
                f" {s['litres_per_day']:5.0f} l/dan"
                f" {s['kwh_per_year']:6.0f} kWh/god"
                f" pojas {s['band_wh']:>6} Wh"
                f" tusevi {s['failed_showers']:3d}/{s['showers']:<4d}"
                f" ({s['failed_pct']:4.1f} %)"
                f"  {time.time() - started:5.1f} s",
                flush=True,
            )

    with open(DATA_DIR / "year_summary.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summaries[0].keys()))
        writer.writeheader()
        writer.writerows(summaries)

    with open(DATA_DIR / "metadata.json", "w") as fh:
        json.dump(
            {
                "year": YEAR,
                "caveat": CAVEAT,
                "weight_source": WEIGHT_SOURCE,
                "collect_only_days": COLLECT_ONLY_DAYS,
                "record_interval_s": 900,
                "timestep_s": 60,
                "public_holidays": sorted(str(d) for d in public_holidays(YEAR)),
                "schema_year_15min": ["archetype", *ROW_FIELDS],
                "field_notes": {
                    "true_stored_wh": "istina, energija iznad temperature mreze - samo za validaciju",
                    "d_lo_wh": "donja granica manjka koju algoritam zna",
                    "d_hi_wh": "gornja granica manjka koju algoritam zna",
                    "shed_available_wh": "koliko se grijanja moze odgoditi (prodaja nadolje)",
                    "absorb_available_wh": "koliko se energije moze primiti na zahtjev (prodaja nagore)",
                },
                "archetypes": [
                    {
                        "id": a.id, "note": a.note, "weight": a.weight,
                        "volume_l": a.spec.volume_l, "power_w": a.spec.element_power_w,
                        "occupants": a.household.occupants,
                        "unheated": a.unheated,
                        "wfh_days_per_week": a.wfh_days_per_week,
                        "annual_leave_weeks": a.annual_leave_weeks,
                        "weekend_only": a.weekend_only,
                        "needs_contactor": a.needs_contactor,
                    }
                    for a in selected
                ],
            },
            fh,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nukupno {time.time() - t0:.0f} s -> {DATA_DIR}")


if __name__ == "__main__":
    main()
