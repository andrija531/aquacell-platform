"""Ten test scenarios: household behaviour paired with real Croatian tank sizes.

Tank size is part of the scenario, not a global constant. An 80 L tank is
comfortable for one person and undersized for four, and that difference drives
almost everything — how often the tank is emptied, whether the capacity can be
measured passively, and how much flexibility exists at all.

Occupancy and usage intensity are kept as separate dimensions so results can be
attributed to one or the other.

Standing loss is scaled from the 80 L reference by surface area, which grows
roughly as V^(2/3): a 30 L tank leaks less in absolute terms but proportionally
more per litre stored.
"""

from __future__ import annotations

from dataclasses import dataclass

from .draws import HouseholdProfile
from .tank import TankSpec

UA_REFERENCE_W_PER_K = 1.47  # for 80 l -> ~50 W standing loss at dT = 34 K
VOLUME_REFERENCE_L = 80.0


def tank(volume_l: float, power_w: float) -> TankSpec:
    """Tank spec with standing loss scaled by surface area."""
    ua = UA_REFERENCE_W_PER_K * (volume_l / VOLUME_REFERENCE_L) ** (2.0 / 3.0)
    return TankSpec(
        volume_l=volume_l,
        n_nodes=12,
        element_node=1,
        probe_node=1,
        probe_span=6,
        ua_w_per_k=ua,
        element_power_w=power_w,
        conduction_w_per_k=0.8 * (volume_l / VOLUME_REFERENCE_L) ** (1.0 / 3.0),
    )


def household(
    name: str,
    occupants: int,
    *,
    showers_per_person: float = 1.0,
    shower_l: float = 40.0,
    small_per_day: float = 12.0,
    bath_prob: float = 0.1,
) -> HouseholdProfile:
    return HouseholdProfile(
        name=name,
        occupants=occupants,
        showers_per_person_per_day=showers_per_person,
        shower_volume_l=shower_l,
        small_draws_per_day=small_per_day,
        bath_probability_per_day=bath_prob,
    )


@dataclass(frozen=True)
class Scenario:
    name: str
    note: str
    household: HouseholdProfile
    tank: TankSpec
    ambient_winter_c: float = 22.0
    ambient_summer_c: float = 26.0

    @property
    def unheated(self) -> bool:
        return self.ambient_winter_c < 15.0


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "S1_samac_30l",
        "garsonjera, mali bojler - najtjesnji slucaj",
        household("samac", 1, small_per_day=8.0, bath_prob=0.0),
        tank(30.0, 1500.0),
    ),
    Scenario(
        "S2_samac_50l",
        "samac, uobicajen mali bojler",
        household("samac", 1, small_per_day=8.0, bath_prob=0.02),
        tank(50.0, 2000.0),
    ),
    Scenario(
        "S3_samac_80l",
        "samac, predimenzioniran bojler - spremnik se nikad ne isprazni",
        household("samac", 1, small_per_day=8.0, bath_prob=0.05),
        tank(80.0, 2000.0),
    ),
    Scenario(
        "S4_par_50l",
        "par, poddimenzioniran bojler",
        household("par", 2, small_per_day=12.0, bath_prob=0.05),
        tank(50.0, 2000.0),
    ),
    Scenario(
        "S5_par_80l",
        "par, tipicna hrvatska kupaonica",
        household("par", 2, small_per_day=12.0, bath_prob=0.10),
        tank(80.0, 2000.0),
    ),
    Scenario(
        "S6_obitelj3_80l",
        "tri clana, 80 l",
        household("obitelj3", 3, small_per_day=16.0, bath_prob=0.15),
        tank(80.0, 2000.0),
    ),
    Scenario(
        "S7_obitelj4_80l",
        "cetiri clana na 80 l - poddimenzionirano, hladni tusevi i bez kontrole",
        household("obitelj4", 4, small_per_day=20.0, bath_prob=0.25),
        tank(80.0, 2000.0),
    ),
    Scenario(
        "S8_obitelj4_120l",
        "cetiri clana, ispravno dimenzionirano",
        household("obitelj4", 4, small_per_day=20.0, bath_prob=0.25),
        tank(120.0, 2400.0),
    ),
    Scenario(
        "S9_obitelj5_120l",
        "pet clanova, 120 l - najveca potrosnja",
        household("obitelj5", 5, small_per_day=24.0, bath_prob=0.30),
        tank(120.0, 2400.0),
    ),
    Scenario(
        "S10_vikendica_80l",
        "niska potrosnja u negrijanom prostoru - test sezonske varijacije L",
        household(
            "niska_potrosnja", 1, showers_per_person=0.6, shower_l=25.0,
            small_per_day=4.0, bath_prob=0.0,
        ),
        tank(80.0, 2000.0),
        ambient_winter_c=8.0,
        ambient_summer_c=24.0,
    ),
)


def by_name(name: str) -> Scenario:
    for s in SCENARIOS:
        if s.name == name or s.name.endswith(name):
            return s
    raise KeyError(name)
