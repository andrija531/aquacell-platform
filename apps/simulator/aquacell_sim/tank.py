"""Stratified multi-node water heater model.

This is the *ground truth* of the simulator: it knows all temperatures.
The estimator under test never sees any of it — only relay state and power.

Physics, per timestep:
  1. element adds heat to its node
  2. draw advects water upward (cold in at the bottom, hot out at the top)
  3. standing loss to ambient, per node
  4. conduction between adjacent nodes
  5. buoyancy: any temperature inversion is mixed away

Node 0 is the bottom. The element sits low, so heated water rises and the
tank fills with heat from the element upward. Water *below* the element is
only reached by conduction, which reproduces the real dead volume at the
bottom of a vertical tank.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

WH_PER_LITRE_KELVIN = 1.163  # specific heat of water, Wh/(l*K)


@dataclass(frozen=True)
class TankSpec:
    volume_l: float = 80.0
    n_nodes: int = 12
    element_node: int = 1
    # A real bottom-flange thermostat is a rod reaching up into the tank, so it
    # senses an average over a vertical span rather than a single point. Probe
    # placement dominates E_hyst, so this is a first-class parameter.
    probe_node: int = 1
    probe_span: int = 6
    ua_w_per_k: float = 1.47  # shell loss coefficient -> ~50 W at dT=34 K
    element_power_w: float = 2000.0
    conduction_w_per_k: float = 0.8  # between adjacent nodes

    @property
    def node_volume_l(self) -> float:
        return self.volume_l / self.n_nodes

    @property
    def node_capacity_wh_per_k(self) -> float:
        return self.node_volume_l * WH_PER_LITRE_KELVIN

    @property
    def total_capacity_wh_per_k(self) -> float:
        return self.volume_l * WH_PER_LITRE_KELVIN


@dataclass
class Environment:
    t_ambient_c: float = 22.0
    t_inlet_c: float = 8.0


@dataclass
class StepResult:
    outlet_temp_c: float
    energy_in_wh: float
    loss_wh: float
    draw_energy_wh: float


class Tank:
    def __init__(
        self,
        spec: TankSpec | None = None,
        env: Environment | None = None,
        t_initial_c: float | None = None,
    ) -> None:
        self.spec = spec or TankSpec()
        self.env = env or Environment()
        t0 = self.env.t_inlet_c if t_initial_c is None else t_initial_c
        self.t = np.full(self.spec.n_nodes, float(t0))

    # ---------------------------------------------------------------- state

    @property
    def probe_temp_c(self) -> float:
        lo = self.spec.probe_node
        hi = min(self.spec.n_nodes, lo + max(1, self.spec.probe_span))
        return float(np.mean(self.t[lo:hi]))

    @property
    def top_temp_c(self) -> float:
        return float(self.t[-1])

    def energy_above_inlet_wh(self) -> float:
        """Ground-truth E_stored: energy held above mains temperature."""
        return float(
            np.sum(self.t - self.env.t_inlet_c) * self.spec.node_capacity_wh_per_k
        )

    def usable_energy_wh(self, t_min_c: float) -> float:
        """Energy held in water that is still above the comfort threshold."""
        hot = np.clip(self.t - t_min_c, 0.0, None)
        return float(np.sum(hot) * self.spec.node_capacity_wh_per_k)

    # ----------------------------------------------------------------- step

    def step(self, dt_s: float, heating: bool, draw_l: float = 0.0) -> StepResult:
        spec = self.spec
        dt_h = dt_s / 3600.0
        c_node = spec.node_capacity_wh_per_k

        outlet = self.top_temp_c
        energy_in = 0.0
        draw_energy = 0.0

        # 1. element
        if heating:
            energy_in = spec.element_power_w * dt_h
            self.t[spec.element_node] += energy_in / c_node

        # 2. draw: upward plug flow. Sub-step if the drawn volume exceeds a node.
        if draw_l > 0.0:
            before = self.energy_above_inlet_wh()
            remaining = draw_l
            max_per_pass = 0.5 * spec.node_volume_l
            while remaining > 1e-12:
                v = min(remaining, max_per_pass)
                remaining -= v
                f = v / spec.node_volume_l
                upstream = np.empty_like(self.t)
                upstream[0] = self.env.t_inlet_c
                upstream[1:] = self.t[:-1]
                self.t += f * (upstream - self.t)
            draw_energy = before - self.energy_above_inlet_wh()

        # 3. standing loss, distributed evenly over nodes
        ua_node = spec.ua_w_per_k / spec.n_nodes
        loss_w = ua_node * (self.t - self.env.t_ambient_c)
        loss_wh = loss_w * dt_h
        self.t -= loss_wh / c_node

        # 4. conduction between neighbours
        if spec.conduction_w_per_k > 0.0:
            flux = spec.conduction_w_per_k * np.diff(self.t) * dt_h  # i -> i+1
            self.t[:-1] += flux / c_node
            self.t[1:] -= flux / c_node

        # 5. buoyancy: eliminate inversions
        self._mix_inversions()

        return StepResult(
            outlet_temp_c=outlet,
            energy_in_wh=energy_in,
            loss_wh=float(np.sum(loss_wh)),
            draw_energy_wh=draw_energy,
        )

    def _mix_inversions(self, max_passes: int = 64) -> None:
        """Merge adjacent layers whenever a lower one is hotter than the one above.

        Scalar loop rather than numpy: for a 12-element array the numpy call
        overhead dominates the arithmetic by roughly an order of magnitude, and
        this runs on every timestep of every simulated household-year.
        """
        t = self.t
        n = len(t)
        for _ in range(max_passes):
            changed = False
            for i in range(n - 1):
                a, b = t[i], t[i + 1]
                if a > b + 1e-9:
                    mean = 0.5 * (a + b)
                    t[i] = mean
                    t[i + 1] = mean
                    changed = True
            if not changed:
                return


class MechanicalThermostat:
    """Bimetallic thermostat with a hysteresis band.

    Closed (calling for heat) until the probe reaches the setpoint, then open
    until the probe falls a full hysteresis band below it.
    """

    def __init__(self, setpoint_c: float = 60.0, hysteresis_k: float = 8.0) -> None:
        self.setpoint_c = setpoint_c
        self.hysteresis_k = hysteresis_k
        self.closed = True

    @property
    def reclose_temp_c(self) -> float:
        return self.setpoint_c - self.hysteresis_k

    def update(self, probe_temp_c: float) -> bool:
        if self.closed and probe_temp_c >= self.setpoint_c:
            self.closed = False
        elif not self.closed and probe_temp_c <= self.reclose_temp_c:
            self.closed = True
        return self.closed
