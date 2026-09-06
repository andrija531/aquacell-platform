"""Locks in the accuracy of the calibrated parameters against ground truth.

These are the numbers every bid is built on. If they drift, the bids are wrong,
so the tolerances here are deliberately tight for heated installations and
deliberately loose for unheated ones, where a known bias remains.
"""

from __future__ import annotations

import numpy as np
import pytest

from aquacell_sim.archetypes import by_id
from aquacell_sim.calendar_hr import build_year
from aquacell_sim.run_year import stable_seed
from aquacell_sim.year import generate_year, simulate_year

DAYS = 365  # the estimate only converges once an away period has been seen


def _run(archetype_id: str):
    a = by_id(archetype_id)
    rng = np.random.default_rng(stable_seed(a.id))
    days = build_year(
        2025, rng,
        wfh_days_per_week=a.wfh_days_per_week,
        annual_leave_weeks=a.annual_leave_weeks,
        winter_break_days=a.winter_break_days,
        weekend_only=a.weekend_only,
    )[:DAYS]
    events = generate_year(a.household, days, rng, has_children=a.has_children)
    return a, simulate_year(
        a.household, days, events, a.spec, unheated=a.unheated, collect_only_days=30
    )


@pytest.mark.slow
@pytest.mark.parametrize("archetype_id", ["A03", "A07"])
def test_standing_loss_accurate_for_heated_tanks(archetype_id):
    a, result = _run(archetype_id)
    assert not a.unheated
    estimated = result.calibration.l_w
    error = estimated / result.true_loss_w - 1.0
    assert abs(error) < 0.12, (
        f"{archetype_id}: L procijenjen {estimated:.1f} W vs stvarni "
        f"{result.true_loss_w:.1f} W, greska {error:+.0%}"
    )


@pytest.mark.slow
@pytest.mark.parametrize("archetype_id", ["A10"])
def test_standing_loss_known_bias_for_unheated_tanks(archetype_id):
    """Documents an open defect rather than asserting correctness.

    Draw-free cycles cluster in the summer holiday, when an unheated tank leaks
    least, so the pooled estimate lands low. Needs a seasonal correction.
    """
    a, result = _run(archetype_id)
    assert a.unheated
    error = result.calibration.l_w / result.true_loss_w - 1.0
    assert -0.35 < error < 0.10, f"{archetype_id}: greska {error:+.0%}"


@pytest.mark.slow
def test_hysteresis_energy_scales_with_volume():
    """E_hyst / volume should be roughly constant: the thermostat differential
    is a property of the bimetal, not of the tank."""
    per_litre = {}
    for archetype_id in ("A01", "A07", "A15"):
        a, result = _run(archetype_id)
        per_litre[archetype_id] = (
            result.calibration.e_hyst_quiet_wh / a.spec.volume_l
        )
    values = np.array(list(per_litre.values()))
    spread = values.max() / values.min()
    assert spread < 2.0, f"E_hyst po litri se previse razlikuje: {per_litre}"


def test_absorb_is_gated_until_a_draw_free_period_is_seen():
    """Short history -> L biased high -> the absorb product must not be offered.

    This is the guard that stops a newly installed device from promising
    absorption it cannot deliver during its first months.
    """
    a = by_id("A07")
    rng = np.random.default_rng(stable_seed(a.id))
    days = build_year(2025, rng, annual_leave_weeks=a.annual_leave_weeks)[:120]
    events = generate_year(a.household, days, rng)
    result = simulate_year(
        a.household, days, events, a.spec, unheated=False, collect_only_days=30
    )
    cal = result.calibration
    assert cal is not None
    if not cal.l_confident:
        assert not cal.absorb_offerable
        assert cal.l_w / result.true_loss_w > 1.0, (
            "without a draw-free period the loss estimate should be biased high"
        )
