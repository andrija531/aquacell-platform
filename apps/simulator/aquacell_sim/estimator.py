"""Interval observer, deficit formulation.

Two problems in the first version, both found by the simulator:

  1. `E_capacity` measured as the largest observed reheat was wrong by −61 %
     to +9 %, and the +9 % direction is unsafe.
  2. The clamp "thermostat open, therefore the tank is nearly full" was false.
     Stratification lets the probe stay warm while the top is hot, the bottom
     is cold, and a lot of energy has already left. 145 breaches in 45 days,
     worst case 1534 Wh — a whole shower.

Both are fixed by changing what is tracked and how the bound is calibrated.

TRACKED QUANTITY: deficit below cut-out, `d`, in Wh. `d = 0` means the
thermostat has just opened. This removes the absolute scale entirely — no
`E_capacity`, no assumption about how much water is below the probe.

    cut-out            -> d = 0                    exact, free, no calibration
    heating            -> d decreases by P*dt      exact
    standing loss      -> d increases by L*dt      calibrated
    unobserved draw    -> d increases, unknown     worst case only
    thermostat open    -> d <= deficit_at_reclose  see below

THE SOUND CLAMP. While the thermostat is open the deficit can only be
smaller than it will be at the moment the thermostat next closes. That
closing deficit is directly measurable: it is the energy of the reheat run
that follows. So a high percentile of observed reclose-to-cut-out energies is
a valid upper bound on the deficit for as long as the thermostat stays open.
Unlike the old clamp, this makes no claim about tank geometry.

THE COMFORT CONSTRAINT is expressed against the measured *sellable band*
rather than against capacity, because energy below the comfort reserve can
never be sold and therefore never needs to be known.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

POWER_ON_THRESHOLD_W = 50.0
QUIET_OFF_PERIOD_S = 4 * 3600.0  # before this, a reclose is not "quiet"


@dataclass
class HeatingRun:
    start_s: float
    energy_wh: float
    from_reclose: bool  # thermostat closed on its own, relay was already closed
    off_period_s: float  # how long the thermostat had been open beforehand
    reached_cutout: bool
    forced: bool  # part of a deliberate calibration night


@dataclass
class Calibration:
    """Everything the observer needs. No temperatures, no volumes, no capacity."""

    l_w: float
    deficit_at_reclose_wh: float  # p95 -> the sound clamp
    band_wh: float  # p20 of calibration nights -> sellable band
    e_hyst_quiet_wh: float  # median of quiet cycles -> diagnostics only
    nominal_power_w: float = 2000.0
    n_calibration_nights: int = 0
    l_confident: bool = False
    n_long_cycles: int = 0

    @property
    def absorb_offerable(self) -> bool:
        """The absorb product must be gated on a trustworthy standing loss.

        Until a genuinely draw-free stretch has been observed - in practice the
        household's first holiday - L is biased 25-60 % high. That is safe for
        shedding (you think the tank cools faster than it does) and unsafe for
        absorbing (you think there is more room than there is, promise energy
        you cannot take, and pay a non-delivery penalty).
        """
        return self.l_confident


class Calibrator:
    """Derives the calibration from observed heating runs only."""

    def __init__(self, nominal_power_w: float = 2000.0) -> None:
        self.nominal_power_w = nominal_power_w
        self.runs: list[HeatingRun] = []
        self._active = False
        self._energy = 0.0
        self._start_s = 0.0
        self._from_reclose = False
        self._off_period_s = 0.0
        self._forced = False
        self._longest_quiet_off_s = 0.0
        self._quiet_cycle_energy: list[float] = []

    def observe(
        self,
        t_s: float,
        dt_s: float,
        relay_closed: bool,
        power_w: float,
        forced: bool = False,
    ) -> None:
        heating = relay_closed and power_w > POWER_ON_THRESHOLD_W

        if heating and not self._active:
            self._active = True
            self._energy = 0.0
            self._start_s = t_s
            self._from_reclose = relay_closed and self._off_period_s > 0.0
            self._off_period_s_at_start = self._off_period_s
            self._forced = forced
            self._off_period_s = 0.0
        elif not heating and self._active:
            self._active = False
            self.runs.append(
                HeatingRun(
                    start_s=self._start_s,
                    energy_wh=self._energy,
                    from_reclose=self._from_reclose,
                    off_period_s=getattr(self, "_off_period_s_at_start", 0.0),
                    reached_cutout=relay_closed,  # if the relay opened, we cut it short
                    forced=self._forced,
                )
            )

        if heating:
            self._energy += power_w * dt_s / 3600.0
        elif relay_closed:
            self._off_period_s += dt_s
        else:
            # relay open: the thermostat is unobservable, so this gap tells us nothing
            self._off_period_s = 0.0

    # ------------------------------------------------------------------ result

    def loss_estimate_w(self, run: HeatingRun) -> float:
        """Duty-cycle loss implied by one complete thermostat cycle.

        With no draws this is exactly the standing loss. Any draw during the
        cycle *adds* reheat energy, so the estimate is one-sided: it can only be
        too high, never too low. The minimum over many cycles therefore
        converges on the truth from above.

        An earlier version divided the median cycle energy by the *longest*
        observed pause, mixing two different statistics, and came out 30-40 %
        high. Overestimating L is safe for the shed product (you think the tank
        cools faster than it does) but unsafe for the absorb product (you think
        there is more room than there is), so it has to be accurate rather than
        conservative.
        """
        cycle_h = (run.off_period_s + run.energy_wh / self.nominal_power_w * 3600.0) / 3600.0
        return run.energy_wh / cycle_h if cycle_h > 0 else float("nan")

    def result(self, at_t_s: float | None = None, window_s: float = 400 * 86400.0):
        """Calibration from the trailing `window_s` of observations.

        The window defaults to the whole history, which is deliberate. Standing
        loss follows the temperature of the room the tank stands in, so a
        rolling window looks like the right answer — but draw-free cycles are
        rare and cluster in periods when the household is away, so a 30-day
        window usually contains none and the estimate lands 15-54 % high.
        Pooling the full history gives 0-6 % error for a tank in a heated room.

        The exception is a tank in an unheated space, where every estimator
        underestimates by 11-20 % because the draw-free cycles come from the
        summer holiday when the loss is at its lowest. Those installs are
        identifiable (their loss distribution varies seasonally) and need a
        separate winter correction. Underestimating the loss is the dangerous
        direction for the shed product, so this is not cosmetic.
        """
        runs = self.runs
        if at_t_s is not None:
            cutoff = at_t_s - window_s
            recent = [r for r in runs if r.start_s >= cutoff]
            if len(recent) >= 30:
                runs = recent

        cutouts = [r for r in runs if r.reached_cutout]
        reclose_runs = [r for r in cutouts if r.from_reclose]
        if len(reclose_runs) < 5:
            return None

        # Sound clamp: worst case, not typical. A bound needs the tail.
        deficit = float(np.percentile([r.energy_wh for r in reclose_runs], 95))

        # Standing loss: the per-cycle estimate is one-sided (draws can only add
        # energy), so a low percentile of the *long* cycles approaches the truth
        # from above. Short cycles are dominated by draws and are excluded.
        long_cycles = [r for r in reclose_runs if r.off_period_s >= QUIET_OFF_PERIOD_S]
        # A pause beyond 10 h can only happen if nobody touched hot water, which
        # in practice means the household was away. Those are the only cycles
        # that pin the standing loss down.
        draw_free = [r for r in reclose_runs if r.off_period_s >= 10 * 3600.0]
        losses = np.array([self.loss_estimate_w(r) for r in long_cycles])
        losses = losses[np.isfinite(losses)]
        l_w = float(np.percentile(losses, 2)) if losses.size >= 10 else 50.0

        e_hyst_quiet = (
            float(np.percentile([r.energy_wh for r in long_cycles], 20))
            if long_cycles
            else deficit
        )

        # Sellable band: deliberate calibration nights only, low percentile so
        # the estimate errs small. It must NOT be coupled to the clamp above —
        # an earlier version took max(band, deficit), which inflated the band to
        # the worst case and let the optimiser shed the tank dry.
        forced_runs = [r.energy_wh for r in cutouts if r.forced]
        if len(forced_runs) >= 3:
            band = float(np.percentile(forced_runs, 20))
        else:
            band = e_hyst_quiet  # conservative until nights accumulate

        return Calibration(
            l_w=l_w,
            deficit_at_reclose_wh=deficit,
            band_wh=band,
            e_hyst_quiet_wh=e_hyst_quiet,
            nominal_power_w=self.nominal_power_w,
            n_calibration_nights=len(forced_runs),
            l_confident=len(draw_free) >= 5,
            n_long_cycles=len(draw_free),
        )


class IntervalObserver:
    """Guaranteed bounds on the deficit below cut-out."""

    def __init__(
        self,
        calibration: Calibration,
        worst_case_draw_wh: Callable[[float, float], float],
    ) -> None:
        self.cal = calibration
        self.worst_case_draw_wh = worst_case_draw_wh
        self.d_lo = 0.0
        self.d_hi = calibration.deficit_at_reclose_wh
        self._heating = False

    @property
    def width_wh(self) -> float:
        return self.d_hi - self.d_lo

    def update(
        self, t_s: float, dt_s: float, relay_closed: bool, power_w: float
    ) -> None:
        cal = self.cal
        dt_h = dt_s / 3600.0
        heating = relay_closed and power_w > POWER_ON_THRESHOLD_W

        if heating:
            gain = power_w * dt_h
            self.d_lo -= gain
            self.d_hi -= gain

        self.d_lo += cal.l_w * dt_h
        self.d_hi += cal.l_w * dt_h
        self.d_hi += self.worst_case_draw_wh(t_s, t_s + dt_s)

        if relay_closed:
            if not heating and self._heating:
                # cut-out: exact, and it costs nothing to obtain
                self.d_lo = self.d_hi = 0.0
            elif not heating:
                # thermostat held open: the sound clamp
                self.d_hi = min(self.d_hi, cal.deficit_at_reclose_wh)

        self._heating = heating
        self.d_lo = max(0.0, self.d_lo)
        self.d_hi = max(self.d_hi, self.d_lo)

    # ------------------------------------------------------------- decisions

    def max_safe_shed_s(
        self, t_s: float, horizon_s: float = 6 * 3600.0, step_s: float = 300.0
    ) -> float:
        """Longest shed keeping the guaranteed deficit inside the sellable band."""
        d = self.d_hi
        elapsed = 0.0
        while elapsed < horizon_s:
            step = min(step_s, horizon_s - elapsed)
            d += self.cal.l_w * step / 3600.0
            d += self.worst_case_draw_wh(t_s + elapsed, t_s + elapsed + step)
            if d > self.cal.band_wh:
                return elapsed
            elapsed += step
        return horizon_s
