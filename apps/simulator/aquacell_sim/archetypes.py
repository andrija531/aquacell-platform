"""Twenty archetypes of Croatian households, with population weights.

WEIGHTS ARE ESTIMATES, NOT DATA. Household size is roughly informed by general
knowledge of Croatian household composition; the distribution of water heater
volumes, the share of tanks in unheated spaces and the share of households
working from home are guesses. They are collected here, in one place, precisely
so they can be replaced without hunting through code.

Replacing them changes every fleet-level number. Nothing else in the simulator
depends on them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .draws import HouseholdProfile
from .scenarios import tank
from .tank import TankSpec

WEIGHT_SOURCE = "procjena (nije mjereno)"


@dataclass(frozen=True)
class Archetype:
    id: str
    note: str
    weight: float
    household: HouseholdProfile
    spec: TankSpec
    unheated: bool = False
    wfh_days_per_week: float = 0.0
    annual_leave_weeks: float = 2.0
    winter_break_days: int = 0
    weekend_only: bool = False
    has_children: bool = False

    @property
    def needs_contactor(self) -> bool:
        """Above the Shelly 1PM Gen3 switching rating of 2000 W."""
        return self.spec.element_power_w > 2000.0


def _hh(
    name: str,
    occupants: int,
    *,
    showers: float = 1.0,
    shower_l: float = 40.0,
    small: float = 12.0,
    bath: float = 0.1,
) -> HouseholdProfile:
    return HouseholdProfile(
        name=name,
        occupants=occupants,
        showers_per_person_per_day=showers,
        shower_volume_l=shower_l,
        small_draws_per_day=small,
        bath_probability_per_day=bath,
    )


ARCHETYPES: tuple[Archetype, ...] = (
    # shower volume is adapted to tank size: a 30 l tank cannot serve a 40 l
    # shower twice, and people learn that within a week of moving in.
    Archetype("A01", "samac, 30 l, garsonjera", 0.05,
              _hh("samac", 1, shower_l=28.0, small=8, bath=0.0), tank(30, 1500)),
    Archetype("A02", "samac, 50 l", 0.06,
              _hh("samac", 1, shower_l=34.0, small=8, bath=0.02), tank(50, 2000)),
    Archetype("A03", "samac, 80 l, predimenzionirano", 0.06,
              _hh("samac", 1, small=8, bath=0.05), tank(80, 2000)),
    Archetype("A04", "samac, 50 l, negrijana kupaonica", 0.02,
              _hh("samac", 1, shower_l=34.0, small=8, bath=0.02), tank(50, 2000),
              unheated=True),
    Archetype("A05", "samac, 80 l, rad od doma 3 dana", 0.03,
              _hh("samac", 1, small=10, bath=0.05), tank(80, 2000),
              wfh_days_per_week=3.0),
    Archetype("A06", "par, 50 l, poddimenzionirano", 0.05,
              _hh("par", 2, shower_l=34.0, small=12), tank(50, 2000)),
    Archetype("A07", "par, 80 l, tipicno", 0.09,
              _hh("par", 2, small=12), tank(80, 2000)),
    Archetype("A08", "par, 80 l, oba rade od doma", 0.04,
              _hh("par", 2, small=16), tank(80, 2000), wfh_days_per_week=4.0),
    Archetype("A09", "par, 100 l", 0.04,
              _hh("par", 2, small=12, bath=0.15), tank(100, 2000)),
    Archetype("A10", "par, 80 l, bojler u podrumu", 0.03,
              _hh("par", 2, small=12), tank(80, 2000), unheated=True),
    Archetype("A11", "obitelj 3, 80 l", 0.08,
              _hh("obitelj3", 3, small=16, bath=0.15), tank(80, 2000),
              has_children=True, annual_leave_weeks=2.5),
    Archetype("A12", "obitelj 3, 100 l", 0.05,
              _hh("obitelj3", 3, small=16, bath=0.15), tank(100, 2000),
              has_children=True, annual_leave_weeks=2.5),
    Archetype("A13", "obitelj 3, 80 l, jedan roditelj od doma", 0.03,
              _hh("obitelj3", 3, small=20, bath=0.15), tank(80, 2000),
              wfh_days_per_week=3.0, has_children=True, annual_leave_weeks=2.5),
    Archetype("A14", "obitelj 4, 80 l, poddimenzionirano", 0.07,
              _hh("obitelj4", 4, small=20, bath=0.25), tank(80, 2000),
              has_children=True, annual_leave_weeks=3.0),
    Archetype("A15", "obitelj 4, 120 l, ispravno", 0.07,
              _hh("obitelj4", 4, small=20, bath=0.25), tank(120, 2400),
              has_children=True, annual_leave_weeks=3.0),
    Archetype("A16", "obitelj 4, 100 l, negrijana kupaonica", 0.03,
              _hh("obitelj4", 4, small=20, bath=0.25), tank(100, 2000),
              unheated=True, has_children=True, annual_leave_weeks=3.0),
    Archetype("A17", "obitelj 5, 120 l", 0.05,
              _hh("obitelj5", 5, small=24, bath=0.30), tank(120, 2400),
              has_children=True, annual_leave_weeks=3.0),
    Archetype("A18", "obitelj 5, 150 l, 3 kW", 0.02,
              _hh("obitelj5", 5, small=24, bath=0.30), tank(150, 3000),
              has_children=True, annual_leave_weeks=3.0),
    Archetype("A19", "vikendica, 80 l, koristena samo vikendom", 0.03,
              _hh("vikend", 2, showers=1.0, small=8, bath=0.2), tank(80, 2000),
              unheated=True, weekend_only=True, annual_leave_weeks=0.0),
    Archetype("A20", "najam / studenti, 80 l, dugi tusevi", 0.10,
              _hh("najam", 2, showers=1.2, shower_l=50.0, small=14, bath=0.05),
              tank(80, 2000), annual_leave_weeks=1.0, winter_break_days=10),
)

assert abs(sum(a.weight for a in ARCHETYPES) - 1.0) < 1e-9, "weights must sum to 1"


def by_id(archetype_id: str) -> Archetype:
    for a in ARCHETYPES:
        if a.id == archetype_id:
            return a
    raise KeyError(archetype_id)
