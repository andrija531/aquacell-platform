"""Sanity tests. These guard the physics, not the business logic."""

from __future__ import annotations

import numpy as np

from aquacell_sim.tank import (
    WH_PER_LITRE_KELVIN,
    Environment,
    MechanicalThermostat,
    Tank,
    TankSpec,
)


def test_energy_conservation_no_loss_no_draw():
    spec = TankSpec(ua_w_per_k=0.0, conduction_w_per_k=0.0)
    env = Environment(t_ambient_c=22.0, t_inlet_c=8.0)
    tank = Tank(spec, env, t_initial_c=20.0)
    before = tank.energy_above_inlet_wh()
    steps, dt = 120, 30.0
    for _ in range(steps):
        tank.step(dt, heating=True)
    expected = spec.element_power_w * steps * dt / 3600.0
    assert abs(tank.energy_above_inlet_wh() - before - expected) < 1e-6


def test_heat_rises_to_the_top():
    """Bottom element must warm the top, not the bottom-most node."""
    tank = Tank(TankSpec(), Environment(), t_initial_c=15.0)
    for _ in range(200):
        tank.step(30.0, heating=True)
    assert tank.t[-1] > tank.t[0], "top should be hotter than the dead bottom node"


def test_draw_pushes_cold_in_at_the_bottom():
    env = Environment(t_inlet_c=8.0)
    tank = Tank(TankSpec(), env, t_initial_c=60.0)
    tank.step(30.0, heating=False, draw_l=10.0)
    assert tank.t[0] < tank.t[-1]
    assert tank.t[0] < 60.0


def test_standing_loss_matches_ua():
    spec = TankSpec(conduction_w_per_k=0.0)
    env = Environment(t_ambient_c=22.0, t_inlet_c=8.0)
    tank = Tank(spec, env, t_initial_c=56.0)
    before = tank.energy_above_inlet_wh()
    tank.step(3600.0, heating=False)
    lost = before - tank.energy_above_inlet_wh()
    expected = spec.ua_w_per_k * (56.0 - 22.0)  # W -> Wh over one hour
    assert abs(lost - expected) / expected < 0.02


def test_idle_cycle_reproduces_expected_timescales():
    """A quiet tank should cycle roughly once every 15 h with ~22 min heating."""
    spec = TankSpec()
    env = Environment(t_ambient_c=22.0, t_inlet_c=8.0)
    tank = Tank(spec, env, t_initial_c=60.0)
    stat = MechanicalThermostat(60.0, 8.0)
    dt = 60.0
    on_s = off_s = 0.0
    transitions = 0
    prev = stat.closed
    for k in range(int(60 * 3600 / dt)):
        closed = stat.update(tank.probe_temp_c)
        tank.step(dt, heating=closed)
        if closed:
            on_s += dt
        else:
            off_s += dt
        if closed != prev:
            transitions += 1
            prev = closed
    duty = on_s / (on_s + off_s)
    standing_loss_w = duty * spec.element_power_w
    assert transitions >= 4, "expected several complete cycles in 60 h"
    assert 30.0 < standing_loss_w < 80.0, f"standing loss {standing_loss_w:.0f} W"


def test_thermostat_hysteresis():
    stat = MechanicalThermostat(60.0, 8.0)
    assert stat.update(55.0) is True
    assert stat.update(59.9) is True
    assert stat.update(60.0) is False
    assert stat.update(53.0) is False
    assert stat.update(52.0) is True
