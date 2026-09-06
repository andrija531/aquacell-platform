"""Experiment harness: ground truth vs. observer, control policies, validation.

Three things are measured:

1. SAFETY — is the guaranteed bound actually guaranteed? Every breach means a
   bid built on it would have been a lie. Target: zero.
2. COMFORT — how many extra cold showers does the control cause, compared with
   an uncontrolled boiler? The baseline is not zero.
3. CAPACITY — the longest shed that can be guaranteed, by hour of day.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .draws import DrawEvent, DrawSchedule, HouseholdProfile
from .estimator import Calibration, Calibrator, IntervalObserver
from .tank import Environment, MechanicalThermostat, Tank, TankSpec

DT_S = 30.0
COLD_SHOWER_TOLERANCE_K = 2.0
COLD_SHOWER_MIN_GOOD_FRACTION = 0.90


@dataclass
class EventOutcome:
    event: DrawEvent
    volume_delivered_l: float = 0.0
    volume_acceptable_l: float = 0.0
    min_delivered_c: float = 999.0

    @property
    def failed(self) -> bool:
        if self.volume_delivered_l <= 0.0:
            return False
        return (
            self.volume_acceptable_l / self.volume_delivered_l
            < COLD_SHOWER_MIN_GOOD_FRACTION
        )

    @property
    def is_shower(self) -> bool:
        return self.event.volume_l >= 20.0


@dataclass
class Trace:
    t_s: list[float] = field(default_factory=list)
    true_deficit_wh: list[float] = field(default_factory=list)
    d_lo: list[float] = field(default_factory=list)
    d_hi: list[float] = field(default_factory=list)
    relay: list[bool] = field(default_factory=list)
    power_w: list[float] = field(default_factory=list)
    draw_energy_wh: list[float] = field(default_factory=list)

    def arrays(self) -> dict[str, np.ndarray]:
        return {k: np.asarray(v) for k, v in self.__dict__.items()}


# ------------------------------------------------------------------- policies


class AlwaysClosed:
    """An ordinary boiler: the mechanical thermostat is in sole charge."""

    forced_window = False

    def __call__(self, t_s: float, observer: IntervalObserver | None) -> bool:
        return True


class CalibrationNight:
    """Defer the refill on selected nights, then heat right through to cut-out.

    Nothing is asked of the customer: their own evening draws empty the tank,
    we simply do not refill it until the small hours. The heating run that
    follows measures the sellable band directly.
    """

    def __init__(
        self,
        every_n_days: int = 7,
        defer_from_h: float = 21.0,
        heat_from_h: float = 1.0,
        heat_until_h: float = 5.0,
    ) -> None:
        self.every_n_days = every_n_days
        self.defer_from_h = defer_from_h
        self.heat_from_h = heat_from_h
        self.heat_until_h = heat_until_h
        self.forced_window = False

    def __call__(self, t_s: float, observer: IntervalObserver | None) -> bool:
        day = int(t_s // 86400)
        hour = (t_s % 86400) / 3600.0
        deferring_day = (day + 1) % self.every_n_days == 0
        heating_day = day % self.every_n_days == 0

        # The deferral must NOT be limited by the band it is trying to measure —
        # an earlier version stopped as soon as d_hi reached the current band
        # estimate, which locked the measurement at its own starting guess and
        # made the calibrated band smaller than a single shower.
        if deferring_day and hour >= self.defer_from_h:
            self.forced_window = False
            return False
        if heating_day and hour < self.heat_from_h:
            self.forced_window = False
            return False
        if heating_day and self.heat_from_h <= hour < self.heat_until_h:
            self.forced_window = True
            return True
        self.forced_window = False
        return True


class AggressiveShed:
    """Shed whenever the observer says it is guaranteed safe. Worst case for comfort."""

    def __init__(self, calibration_night: CalibrationNight | None = None) -> None:
        self.night = calibration_night
        self.forced_window = False
        self._shed_until_s: float | None = None

    def __call__(self, t_s: float, observer: IntervalObserver | None) -> bool:
        if self.night is not None:
            closed = self.night(t_s, observer)
            self.forced_window = self.night.forced_window
            if not closed or self.forced_window:
                return closed
        if observer is None:
            return True
        if self._shed_until_s is not None and t_s < self._shed_until_s:
            return False
        self._shed_until_s = None
        shed_s = observer.max_safe_shed_s(t_s)
        if shed_s >= 900.0:  # only bother with sheds of 15 min or more
            self._shed_until_s = t_s + shed_s
            return False
        return True


# ------------------------------------------------------------------------ run


def resolve_draw(
    tap_l: float, tap_temp_c: float, outlet_c: float, inlet_c: float
) -> tuple[float, float]:
    """Split a tap demand into tank water and cold water."""
    if tap_l <= 0.0:
        return 0.0, 0.0
    if outlet_c <= tap_temp_c + 1e-9:
        return tap_l, outlet_c
    fraction = (tap_temp_c - inlet_c) / (outlet_c - inlet_c)
    return tap_l * max(0.0, min(1.0, fraction)), tap_temp_c


def run(
    profile: HouseholdProfile,
    days: int,
    env: Environment,
    spec: TankSpec | None = None,
    setpoint_c: float = 60.0,
    hysteresis_k: float = 8.0,
    seed: int = 0,
    policy=None,
    calibration: Calibration | None = None,
    worst_case_draw_wh=None,
    trace_every: int = 10,
) -> dict:
    from . import draws as draws_mod

    spec = spec or TankSpec()
    policy = policy or AlwaysClosed()
    tank = Tank(spec, env, t_initial_c=setpoint_c - hysteresis_k / 2)
    stat = MechanicalThermostat(setpoint_c, hysteresis_k)
    schedule = DrawSchedule(draws_mod.generate(profile, days, seed=seed))
    outcomes: dict[int, EventOutcome] = {}

    calibrator = Calibrator(nominal_power_w=spec.element_power_w)
    observer = (
        IntervalObserver(calibration, worst_case_draw_wh)
        if calibration is not None and worst_case_draw_wh is not None
        else None
    )
    trace = Trace()
    e_at_cutout: float | None = None
    prev_thermostat = stat.closed

    for k in range(int(days * 86400 / DT_S)):
        t_s = k * DT_S
        relay_closed = policy(t_s, observer)
        forced = bool(getattr(policy, "forced_window", False))

        thermostat_closed = stat.update(tank.probe_temp_c)
        if prev_thermostat and not thermostat_closed:
            e_at_cutout = tank.energy_above_inlet_wh()
        prev_thermostat = thermostat_closed

        heating = relay_closed and thermostat_closed
        power_w = spec.element_power_w if heating else 0.0

        tap_l, tap_temp, event = schedule.demand(t_s, DT_S)
        tank_l, delivered_c = resolve_draw(
            tap_l, tap_temp, tank.top_temp_c, env.t_inlet_c
        )
        if event is not None and tap_l > 0.0:
            oc = outcomes.setdefault(id(event), EventOutcome(event))
            oc.volume_delivered_l += tap_l
            oc.min_delivered_c = min(oc.min_delivered_c, delivered_c)
            if delivered_c >= event.tap_temp_c - COLD_SHOWER_TOLERANCE_K:
                oc.volume_acceptable_l += tap_l

        result = tank.step(DT_S, heating=heating, draw_l=tank_l)
        calibrator.observe(t_s, DT_S, relay_closed, power_w, forced=forced)
        if observer is not None:
            observer.update(t_s, DT_S, relay_closed, power_w)

        if k % trace_every == 0:
            trace.t_s.append(t_s)
            true_deficit = (
                e_at_cutout - tank.energy_above_inlet_wh()
                if e_at_cutout is not None
                else float("nan")
            )
            trace.true_deficit_wh.append(true_deficit)
            trace.d_lo.append(observer.d_lo if observer else float("nan"))
            trace.d_hi.append(observer.d_hi if observer else float("nan"))
            trace.relay.append(relay_closed)
            trace.power_w.append(power_w)
            trace.draw_energy_wh.append(result.draw_energy_wh)

    showers = [o for o in outcomes.values() if o.is_shower]
    return {
        "calibration": calibrator.result(),
        "calibrator": calibrator,
        "observer": observer,
        "trace": trace,
        "outcomes": list(outcomes.values()),
        "n_showers": len(showers),
        "n_failed_showers": sum(1 for o in showers if o.failed),
        "shed_fraction": float(
            1.0 - np.mean(np.asarray(trace.relay, dtype=float))
        ),
        "energy_wh": float(np.sum(trace.power_w) * DT_S * trace_every / 3600.0),
    }


# --------------------------------------------------------- draw statistics


def hourly_draw_energy(trace: Trace) -> np.ndarray:
    a = trace.arrays()
    hours = (a["t_s"] // 3600).astype(int)
    out = np.zeros(hours.max() + 1)
    np.add.at(out, hours, a["draw_energy_wh"])
    return out


def draw_quantiles(hourly: np.ndarray, q: float) -> np.ndarray:
    n_days = len(hourly) // 24
    grid = hourly[: n_days * 24].reshape(n_days, 24)
    return np.percentile(grid, q * 100.0, axis=0)


def make_worst_case_draw(per_hour_wh: np.ndarray):
    def worst_case(t_from_s: float, t_to_s: float) -> float:
        total = 0.0
        t = t_from_s
        while t < t_to_s:
            hour_idx = int(t // 3600)
            hour_end = (hour_idx + 1) * 3600.0
            span = min(hour_end, t_to_s) - t
            total += per_hour_wh[hour_idx % 24] * span / 3600.0
            t = min(hour_end, t_to_s)
        return total

    return worst_case
