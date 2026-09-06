"""Full-year simulation: calendar-aware behaviour, seasonal environment, recording.

Draw behaviour changes with the day type, which is where most of the realism
comes from:

  radni dan     sharp 06-08 peak, evening 18-21
  rad od doma   softer morning, extra midday draws
  subota        morning shifted to 08-11, more baths
  nedjelja      later still
  praznik       like Sunday
  odsutni       nothing at all (annual leave, weekend flat left empty)

School holidays add midday draws for households with children. Winter showers
are slightly longer. Occasional guest days add extra showers.

Recorded at market resolution (15 min) so a row can be read directly as "what
could have been offered for this MTU".
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np

from .calendar_hr import (
    DayContext,
    DayType,
    ambient_temp_c,
    inlet_temp_c,
    shower_seasonal_factor,
)
from .draws import DrawEvent, DrawSchedule, HouseholdProfile
from .estimator import Calibrator, IntervalObserver
from .experiment import (
    COLD_SHOWER_MIN_GOOD_FRACTION,
    COLD_SHOWER_TOLERANCE_K,
    EventOutcome,
    resolve_draw,
)
from .tank import Environment, MechanicalThermostat, Tank, TankSpec

# Hour-of-day weights for shower placement, per day type. Estimates.
SHOWER_WEIGHTS: dict[DayType, tuple[float, ...]] = {
    DayType.WORKDAY: (
        0.05, 0.03, 0.03, 0.03, 0.15, 1.2, 4.5, 5.0, 2.0, 0.6, 0.4, 0.4,
        0.5, 0.5, 0.5, 0.7, 1.2, 2.2, 3.2, 2.8, 1.8, 1.0, 0.4, 0.1,
    ),
    DayType.WFH: (
        0.05, 0.03, 0.03, 0.03, 0.10, 0.5, 2.0, 3.2, 3.0, 1.6, 0.9, 0.7,
        0.8, 0.8, 0.7, 0.8, 1.2, 2.0, 2.8, 2.4, 1.6, 0.9, 0.4, 0.1,
    ),
    DayType.SATURDAY: (
        0.15, 0.10, 0.05, 0.03, 0.05, 0.2, 0.6, 1.4, 2.6, 3.2, 2.8, 1.8,
        1.2, 1.0, 1.0, 1.1, 1.4, 1.8, 2.4, 2.4, 2.0, 1.4, 0.8, 0.3,
    ),
    DayType.SUNDAY: (
        0.20, 0.12, 0.06, 0.03, 0.05, 0.15, 0.4, 0.9, 1.8, 2.8, 3.0, 2.2,
        1.4, 1.0, 0.9, 1.0, 1.3, 1.8, 2.6, 2.6, 2.0, 1.2, 0.6, 0.2,
    ),
}
SHOWER_WEIGHTS[DayType.HOLIDAY] = SHOWER_WEIGHTS[DayType.SUNDAY]

SMALL_WEIGHTS: dict[DayType, tuple[float, ...]] = {
    DayType.WORKDAY: (
        0.05, 0.03, 0.03, 0.03, 0.1, 0.6, 1.4, 1.6, 0.8, 0.4, 0.4, 0.6,
        0.9, 0.6, 0.4, 0.5, 0.9, 1.8, 2.4, 2.0, 1.5, 0.9, 0.4, 0.1,
    ),
    DayType.WFH: (
        0.05, 0.03, 0.03, 0.03, 0.1, 0.4, 1.0, 1.4, 1.4, 1.3, 1.3, 1.6,
        2.0, 1.6, 1.3, 1.3, 1.4, 1.8, 2.2, 1.9, 1.4, 0.9, 0.4, 0.1,
    ),
    DayType.SATURDAY: (
        0.1, 0.06, 0.03, 0.03, 0.05, 0.2, 0.5, 0.9, 1.4, 1.8, 1.8, 1.8,
        2.0, 1.6, 1.3, 1.3, 1.5, 1.9, 2.2, 2.0, 1.6, 1.1, 0.6, 0.2,
    ),
}
SMALL_WEIGHTS[DayType.SUNDAY] = SMALL_WEIGHTS[DayType.SATURDAY]
SMALL_WEIGHTS[DayType.HOLIDAY] = SMALL_WEIGHTS[DayType.SATURDAY]
SMALL_WEIGHTS[DayType.WORKDAY] = SMALL_WEIGHTS[DayType.WORKDAY]


def _place(rng: np.random.Generator, weights: tuple[float, ...], n: int) -> np.ndarray:
    w = np.asarray(weights, dtype=float)
    hours = rng.choice(24, size=n, p=w / w.sum())
    return hours * 3600.0 + rng.uniform(0.0, 3600.0, size=n)


class DenseSchedule:
    """Draw demand precomputed per timestep.

    The event list used to be scanned linearly on every step, which for a year
    at 60 s and a couple of thousand events is around a billion comparisons and
    dominated the whole simulation. Precomputing costs a few megabytes.
    """

    def __init__(self, events: list[DrawEvent], n_steps: int, dt_s: float) -> None:
        self.litres = np.zeros(n_steps)
        self.tap_temp = np.zeros(n_steps)
        self.event_index = np.full(n_steps, -1, dtype=np.int32)
        self.events = events
        for idx, event in enumerate(events):
            first = int(event.start_s // dt_s)
            last = min(n_steps - 1, int(event.end_s // dt_s))
            if first >= n_steps:
                continue
            per_step = event.flow_l_per_min / 60.0 * dt_s
            for k in range(first, last + 1):
                # later events win a collision; overlaps are rare and small
                self.litres[k] = per_step
                self.tap_temp[k] = event.tap_temp_c
                self.event_index[k] = idx


def generate_year(
    profile: HouseholdProfile,
    days: list[DayContext],
    rng: np.random.Generator,
    has_children: bool = False,
    guest_probability_per_day: float = 0.02,
) -> list[DrawEvent]:
    events: list[DrawEvent] = []

    for index, day in enumerate(days):
        offset = index * 86400.0
        if day.day_type is DayType.AWAY:
            continue

        season = shower_seasonal_factor(day.day_of_year)
        shower_w = SHOWER_WEIGHTS[day.day_type]
        small_w = SMALL_WEIGHTS[day.day_type]

        occupants = profile.occupants
        if rng.random() < guest_probability_per_day:
            occupants += int(rng.integers(1, 3))

        n_showers = rng.poisson(occupants * profile.showers_per_person_per_day)
        for start in _place(rng, shower_w, n_showers):
            volume = rng.normal(profile.shower_volume_l, profile.shower_volume_l * 0.2)
            events.append(
                DrawEvent(
                    start_s=offset + float(start),
                    volume_l=max(8.0, float(volume) * season),
                    tap_temp_c=float(rng.normal(profile.shower_tap_temp_c, 1.0)),
                    flow_l_per_min=profile.shower_flow_l_per_min,
                )
            )

        small_rate = profile.small_draws_per_day
        if day.relaxed or day.day_type is DayType.WFH:
            small_rate *= 1.35
        if day.school_holiday and has_children:
            small_rate *= 1.25
        for start in _place(rng, small_w, rng.poisson(small_rate)):
            events.append(
                DrawEvent(
                    start_s=offset + float(start),
                    volume_l=max(0.5, float(rng.exponential(profile.small_volume_l))),
                    tap_temp_c=profile.small_tap_temp_c,
                    flow_l_per_min=4.0,
                )
            )

        bath_p = profile.bath_probability_per_day * (2.0 if day.relaxed else 1.0)
        if rng.random() < bath_p:
            start = _place(rng, shower_w, 1)[0]
            events.append(
                DrawEvent(
                    start_s=offset + float(start),
                    volume_l=profile.bath_volume_l,
                    tap_temp_c=40.0,
                    flow_l_per_min=12.0,
                )
            )

    return sorted(events, key=lambda e: e.start_s)


# ------------------------------------------------------------------ simulation

ROW_FIELDS = (
    "t_s",
    "date",
    "hour",
    "day_type",
    "inlet_c",
    "ambient_c",
    "true_stored_wh",
    "true_deficit_wh",
    "d_lo_wh",
    "d_hi_wh",
    "band_wh",
    "l_w",
    "draw_wh",
    "energy_in_wh",
    "relay_closed_frac",
    "thermostat_closed_frac",
    "shed_available_wh",
    "shed_available_min",
    "absorb_available_wh",
    "absorb_available_min",
)


@dataclass
class YearResult:
    rows: list[tuple]
    events: list[tuple]
    calibration: object
    calibrator: object
    outcomes: list[EventOutcome]
    litres_per_day: float
    true_loss_w: float


def simulate_year(
    profile: HouseholdProfile,
    days: list[DayContext],
    draw_events: list[DrawEvent],
    spec: TankSpec,
    unheated: bool,
    setpoint_c: float = 60.0,
    hysteresis_k: float = 8.0,
    dt_s: float = 60.0,
    record_s: float = 900.0,
    collect_only_days: int = 30,
    calibration_every_n_days: int = 7,
    defer_from_h: float = 17.0,
    heat_from_h: float = 1.0,
    heat_until_h: float = 5.0,
) -> YearResult:
    """One household, one year. First `collect_only_days` are observation only."""
    env = Environment(
        ambient_temp_c(days[0].day_of_year, unheated), inlet_temp_c(days[0].day_of_year)
    )
    tank = Tank(spec, env, t_initial_c=setpoint_c - hysteresis_k / 2)
    stat = MechanicalThermostat(setpoint_c, hysteresis_k)
    n_steps = int(len(days) * 86400 / dt_s)
    schedule = DenseSchedule(draw_events, n_steps, dt_s)
    calibrator = Calibrator(nominal_power_w=spec.element_power_w)
    observer: IntervalObserver | None = None
    outcomes: dict[int, EventOutcome] = {}

    rows: list[tuple] = []
    event_log: list[tuple] = []
    steps_per_record = max(1, int(record_s / dt_s))
    acc = {
        "draw": 0.0, "energy": 0.0, "relay": 0.0, "stat": 0.0, "n": 0,
    }
    e_at_cutout: float | None = None
    prev_stat = stat.closed
    hourly_worst = np.zeros(24)
    true_loss_wh = 0.0

    for k in range(n_steps):
        t_s = k * dt_s
        day_index = int(t_s // 86400)
        day = days[min(day_index, len(days) - 1)]
        hour = (t_s % 86400) / 3600.0

        if k % int(86400 / dt_s) == 0:
            env.t_inlet_c = inlet_temp_c(day.day_of_year)
            env.t_ambient_c = ambient_temp_c(day.day_of_year, unheated)

        # ---- relay policy: observation only, then weekly calibration nights
        forced = False
        relay_closed = True
        if day_index >= collect_only_days:
            deferring = (day_index + 1) % calibration_every_n_days == 0
            heating_day = day_index % calibration_every_n_days == 0
            if deferring and hour >= defer_from_h:
                relay_closed = False
            elif heating_day and hour < heat_from_h:
                relay_closed = False
            elif heating_day and heat_from_h <= hour < heat_until_h:
                forced = True

        thermostat_closed = stat.update(tank.probe_temp_c)
        if prev_stat and not thermostat_closed:
            e_at_cutout = tank.energy_above_inlet_wh()
            event_log.append((round(t_s), str(day.date), "isklop", round(tank.top_temp_c, 1)))
        elif not prev_stat and thermostat_closed:
            event_log.append((round(t_s), str(day.date), "uklop", round(tank.top_temp_c, 1)))
        prev_stat = thermostat_closed

        heating = relay_closed and thermostat_closed
        power_w = spec.element_power_w if heating else 0.0

        tap_l = schedule.litres[k]
        event_idx = schedule.event_index[k]
        tank_l = 0.0
        if tap_l > 0.0:
            tap_temp = schedule.tap_temp[k]
            tank_l, delivered_c = resolve_draw(
                tap_l, tap_temp, tank.top_temp_c, env.t_inlet_c
            )
            event = schedule.events[event_idx]
            oc = outcomes.setdefault(event_idx, EventOutcome(event))
            oc.volume_delivered_l += tap_l
            oc.min_delivered_c = min(oc.min_delivered_c, delivered_c)
            if delivered_c >= event.tap_temp_c - COLD_SHOWER_TOLERANCE_K:
                oc.volume_acceptable_l += tap_l

        result = tank.step(dt_s, heating=heating, draw_l=tank_l)
        calibrator.observe(t_s, dt_s, relay_closed, power_w, forced=forced)
        hourly_worst[int(hour)] += result.draw_energy_wh

        # Refresh the calibration weekly: standing loss tracks the room
        # temperature, so a figure fixed at commissioning drifts with the season.
        if day_index >= collect_only_days and k % int(7 * 86400 / dt_s) == 0:
            cal = calibrator.result(at_t_s=t_s)
            if cal is not None:
                per_hour = hourly_worst / max(1, collect_only_days)
                if observer is None:
                    observer = IntervalObserver(cal, _budget(per_hour * 2.0))
                else:
                    observer.cal = cal
        if observer is not None:
            observer.update(t_s, dt_s, relay_closed, power_w)

        true_loss_wh += result.loss_wh
        acc["draw"] += result.draw_energy_wh
        acc["energy"] += result.energy_in_wh
        acc["relay"] += 1.0 if relay_closed else 0.0
        acc["stat"] += 1.0 if thermostat_closed else 0.0
        acc["n"] += 1

        if (k + 1) % steps_per_record == 0:
            n = acc["n"]
            band = observer.cal.band_wh if observer else float("nan")
            d_lo = observer.d_lo if observer else float("nan")
            d_hi = observer.d_hi if observer else float("nan")
            shed_wh = max(0.0, band - d_hi) if observer else float("nan")
            absorb_wh = d_lo if observer else float("nan")
            rows.append(
                (
                    round(t_s), str(day.date), round(hour, 2), day.day_type.value,
                    round(env.t_inlet_c, 2), round(env.t_ambient_c, 2),
                    round(tank.energy_above_inlet_wh(), 1),
                    round(e_at_cutout - tank.energy_above_inlet_wh(), 1)
                    if e_at_cutout is not None else "",
                    round(d_lo, 1) if observer else "",
                    round(d_hi, 1) if observer else "",
                    round(band, 1) if observer else "",
                    round(observer.cal.l_w, 2) if observer else "",
                    round(acc["draw"], 1), round(acc["energy"], 1),
                    round(acc["relay"] / n, 3), round(acc["stat"] / n, 3),
                    round(shed_wh, 1) if observer else "",
                    round(shed_wh / spec.element_power_w * 60.0, 1) if observer else "",
                    round(absorb_wh, 1) if observer else "",
                    round(absorb_wh / spec.element_power_w * 60.0, 1) if observer else "",
                )
            )
            acc = {"draw": 0.0, "energy": 0.0, "relay": 0.0, "stat": 0.0, "n": 0}

    litres = sum(e.volume_l for e in draw_events) / len(days)
    return YearResult(
        rows=rows, events=event_log, calibration=calibrator.result(),
        calibrator=calibrator, outcomes=list(outcomes.values()),
        litres_per_day=litres,
        true_loss_w=true_loss_wh / (len(days) * 24.0),
    )


def _budget(per_hour_wh: np.ndarray):
    def worst_case(t_from_s: float, t_to_s: float) -> float:
        total = 0.0
        t = t_from_s
        while t < t_to_s:
            idx = int(t // 3600)
            end = (idx + 1) * 3600.0
            span = min(end, t_to_s) - t
            total += per_hour_wh[idx % 24] * span / 3600.0
            t = min(end, t_to_s)
        return total

    return worst_case
