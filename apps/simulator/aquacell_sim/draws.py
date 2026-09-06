"""Synthetic domestic hot water draw profiles.

Shaped after the event-based approach used by DHWcalc / EN 16147 tapping
cycles: discrete events of a few types, placed stochastically across the day
with morning and evening peaks.

A draw is expressed as *delivered* water at the tap (litres at a target
temperature). How much of it comes out of the tank depends on the tank's
outlet temperature, which the tank model resolves. That is deliberate: it is
what makes a cold shower observable rather than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DrawEvent:
    start_s: float
    volume_l: float
    tap_temp_c: float
    flow_l_per_min: float

    @property
    def duration_s(self) -> float:
        return self.volume_l / self.flow_l_per_min * 60.0

    @property
    def end_s(self) -> float:
        return self.start_s + self.duration_s


@dataclass(frozen=True)
class HouseholdProfile:
    """Behavioural description of one household."""

    name: str
    occupants: int
    showers_per_person_per_day: float = 1.0
    shower_volume_l: float = 40.0
    shower_tap_temp_c: float = 40.0
    shower_flow_l_per_min: float = 8.0
    small_draws_per_day: float = 12.0
    small_volume_l: float = 4.0
    small_tap_temp_c: float = 38.0
    bath_probability_per_day: float = 0.1
    bath_volume_l: float = 120.0
    # hour-of-day weights for shower placement (24 values, unnormalised)
    shower_hour_weights: tuple[float, ...] = (
        0.1, 0.05, 0.05, 0.05, 0.1, 0.5, 2.0, 5.0, 4.0, 2.0, 1.0, 0.8,
        0.8, 0.8, 0.8, 1.0, 1.5, 2.5, 3.5, 3.0, 2.0, 1.2, 0.6, 0.2,
    )
    small_hour_weights: tuple[float, ...] = (
        0.1, 0.05, 0.05, 0.05, 0.1, 0.3, 1.0, 1.5, 1.2, 1.0, 1.0, 1.5,
        2.0, 1.5, 1.0, 1.0, 1.2, 2.0, 2.5, 2.0, 1.5, 1.0, 0.5, 0.2,
    )


FAMILY_OF_FOUR = HouseholdProfile(
    name="obitelj_4", occupants=4, small_draws_per_day=20.0,
    bath_probability_per_day=0.25,
)
COUPLE = HouseholdProfile(name="par_2", occupants=2, small_draws_per_day=12.0)
# Occupancy and usage intensity are separate dimensions. An earlier version
# bundled them ("single_low_use" also showered less often and for less time),
# which confounded the experiment: it was impossible to tell whether a result
# came from having one occupant or from that occupant using less.
SINGLE = HouseholdProfile(
    name="samac_1", occupants=1, small_draws_per_day=8.0,
    bath_probability_per_day=0.05,
)
# Genuinely low intensity, independent of occupancy: short showers, little else.
# Think a weekend flat, or someone who showers at the gym.
LOW_INTENSITY = HouseholdProfile(
    name="niska_potrosnja", occupants=1, showers_per_person_per_day=0.6,
    shower_volume_l=25.0, small_draws_per_day=4.0,
    bath_probability_per_day=0.0,
)
ALL_PROFILES = (FAMILY_OF_FOUR, COUPLE, SINGLE, LOW_INTENSITY)


def _place(rng: np.random.Generator, weights: tuple[float, ...], n: int) -> np.ndarray:
    """Draw n start times (seconds into the day) from hourly weights."""
    w = np.asarray(weights, dtype=float)
    hours = rng.choice(24, size=n, p=w / w.sum())
    return hours * 3600.0 + rng.uniform(0.0, 3600.0, size=n)


def generate_day(
    profile: HouseholdProfile, rng: np.random.Generator, day_index: int = 0
) -> list[DrawEvent]:
    events: list[DrawEvent] = []

    n_showers = rng.poisson(profile.occupants * profile.showers_per_person_per_day)
    for start in _place(rng, profile.shower_hour_weights, n_showers):
        volume = float(rng.normal(profile.shower_volume_l, profile.shower_volume_l * 0.2))
        events.append(
            DrawEvent(
                start_s=float(start),
                volume_l=max(8.0, volume),
                tap_temp_c=float(rng.normal(profile.shower_tap_temp_c, 1.0)),
                flow_l_per_min=profile.shower_flow_l_per_min,
            )
        )

    n_small = rng.poisson(profile.small_draws_per_day)
    for start in _place(rng, profile.small_hour_weights, n_small):
        events.append(
            DrawEvent(
                start_s=float(start),
                volume_l=max(0.5, float(rng.exponential(profile.small_volume_l))),
                tap_temp_c=profile.small_tap_temp_c,
                flow_l_per_min=4.0,
            )
        )

    if rng.random() < profile.bath_probability_per_day:
        start = _place(rng, profile.shower_hour_weights, 1)[0]
        events.append(
            DrawEvent(
                start_s=float(start),
                volume_l=profile.bath_volume_l,
                tap_temp_c=40.0,
                flow_l_per_min=12.0,
            )
        )

    offset = day_index * 86400.0
    return sorted(
        (
            DrawEvent(e.start_s + offset, e.volume_l, e.tap_temp_c, e.flow_l_per_min)
            for e in events
        ),
        key=lambda e: e.start_s,
    )


def generate(
    profile: HouseholdProfile, days: int, seed: int = 0
) -> list[DrawEvent]:
    rng = np.random.default_rng(seed)
    events: list[DrawEvent] = []
    for day in range(days):
        events.extend(generate_day(profile, rng, day))
    return events


class DrawSchedule:
    """Turns a list of events into a per-timestep tap demand."""

    def __init__(self, events: list[DrawEvent]) -> None:
        self.events = sorted(events, key=lambda e: e.start_s)

    def demand(self, t_s: float, dt_s: float) -> tuple[float, float, DrawEvent | None]:
        """Return (delivered litres wanted, target temp, active event)."""
        for event in self.events:
            if event.start_s <= t_s < event.end_s:
                litres = event.flow_l_per_min / 60.0 * dt_s
                return litres, event.tap_temp_c, event
        return 0.0, 0.0, None
