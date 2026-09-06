# Technical Review, Part 1 — State Estimation

Verdict: the sensorless thesis is sound, but the estimator as specified is formulated in
the wrong units, over-trusts one of its two anchors, and is blind exactly when it earns money.
Three changes fix most of it.

## 1. Reformulate in energy (kWh), not normalised temperature

The recursion `SoC_{k+1} = α·SoC_k + β·P_k − γ·D_k − L_k` is not a valid discretisation.
Standing loss is proportional to `(T_tank − T_amb)`, not to `(T_tank − T_min)`, so `α·SoC`
only holds if `T_amb = T_min`. Correct affine form:

```
SoC_{k+1} = SoC_k·(1 − Δt(UA + ṁcp)/C)
          + Δt/C · [ ηP_k + UA(T_amb − T_min) + ṁcp(T_in − T_min) ] / (T_max − T_min)
```

The offset term carries `T_amb` and `T_inlet` and is not optional — mains inlet in Zagreb
swings ~8 °C winter to ~18 °C summer, a ~25 % change in energy per litre drawn.

Better: drop temperature entirely. Every observable you have is an energy or a duration.
Track `E_k` = kWh stored above the cold-shower threshold:

```
E_{k+1} = E_k + η·P_k·Δt − L·Δt − D_k        (η ≈ 1 for a resistive element)
```

This matters because **`UA` and `C` are not separately identifiable from power-only data.**
Cooling gives you the time constant `τ = C/UA`; reheat gives you `C/η`. You only escape
because `η ≈ 1` for resistive immersion heaters. In energy units you never need to
disentangle them.

### Consequence: the weekly SciPy curve fit is unnecessary

You cannot fit a cooling *curve* — you never see temperature. What you actually observe on
a quiet night is a sequence of thermostat cycles: cut-out at `t0`, dead time `D_off`,
snap-close at `t1`, reheat `D_on`, cut-out at `t2`. From that, arithmetic:

- **Standing loss power** `L = P_nom · D_on / (D_on + D_off)` — i.e. the idle duty cycle × nameplate. Directly measured, no solver.
- **Hysteresis band energy** `E_hyst = P_nom · D_on` — the usable energy between the thermostat's two trip points, in kWh. You never need `ΔT_hyst` in kelvin.
- **Full tank energy** `E_full` — measured once from a deep reheat (relay held off long enough for a real drawdown, then reheat to cut-out).

Replace `thermal_model.py`'s GEKKO/SciPy fit with a robust median over the last N quiet
cycles. It is more accurate, has no convergence failures, and runs in microseconds.

## 2. The 100 % anchor is precise but biased; state the bias explicitly

Thermostat cut-out does not mean "tank full". It means *the water at the bimetallic probe's
height* reached setpoint. The probe sits in the element flange sheath, low-to-mid tank.
Cut-out therefore means "the thermocline has descended past the probe" — close to full for a
vertical bottom-element tank, materially less for a horizontal tank (common in Croatian
80 L bathroom installs, and poorly stratifying).

So the anchor kills *drift* but installs a *constant bias*. The fix is definitional: set
`E_full ≡ ∫P dt` measured over a full deep reheat to cut-out. SoC becomes
`E_k / E_full` — self-consistent, observable, and the bias is absorbed into the
denominator. Do not define SoC against a temperature you cannot measure.

Also flag: if the homeowner turns the thermostat knob, `E_full` and `E_hyst` both change.
Needs change-point detection on `E_hyst` per device, and an alert.

## 3. Active probe pulses — the single highest-value addition

The architecture's real limit is information-theoretic and the report understates it:
**when `R = 0`, the mechanical thermostat state `M` is unobservable.** No current flows
either way, so you learn nothing. You are pure dead-reckoning precisely during the
revenue-generating shed, and the hidden-draw deduction only tells you afterwards how bad
it got. Confidence is worst exactly when accuracy matters most.

Fix: during a shed, close the relay for 2–3 s.

- `P > 0` ⇒ `M = 1` ⇒ tank is **below** the thermostat's reclose point.
- `P = 0` ⇒ `M = 0` ⇒ tank is still **above** it.

Cost: 3 s × 2 kW ≈ 1.7 Wh. Invisible to the customer, invisible to the grid, invisible to
your delivered-capacity measurement if you stagger probes across the fleet.

This converts a blind interval into a stream of **interval-censored observations**, which
is exactly the likelihood a particle filter wants. It collapses the confidence interval that
otherwise forces you into conservative sheds, and it directly buys you longer, more valuable
mFRR sheds.

Constraint to respect: relay cycle life (see Part 2). Probe adaptively — only when posterior
variance exceeds a threshold — not on a fixed timer.

## 4. Use an interval observer for MVP, a particle filter later; skip the EKF

An EKF is the wrong tool. The system is *hybrid*: continuous stored energy, a discrete
latent thermostat mode, and unobserved discrete draw events with a zero-inflated,
heavy-tailed volume distribution. The anchors are not Gaussian measurements — they are
inequality constraints becoming active. Gaussian linearisation misrepresents all of that.

- **MVP: set-membership / interval observer.** Maintain `[E_min, E_max]` propagated with
  worst-case and best-case draw and loss. Anchors clamp the interval; probe pulses split it.
  Cheap enough for Erlang, gives *guaranteed* bounds, and feeds a robust MPC directly.
  Ten lines of arithmetic, no tuning, no divergence.
- **Later: particle filter** in Python. 200–500 particles per device is ~200 float ops per
  update; 50 k devices at one update per 10 s is ~1 MFLOP/s. Compute is a non-issue; the
  cost is code complexity, which is why it belongs in the slow layer, not in Erlang.

Two-tier estimator mirroring the two-tier architecture: Erlang runs the cheap integrator +
hard anchors on the millisecond path; Python runs the Bayesian posterior every 1–5 min and
pushes it back down.

## 5. Skip PINNs for Phases 0–2

The unknowns are three to five scalars. A PINN is a heavyweight, poorly-identifiable,
hard-to-debug way to estimate `UA`, `C`, `η` and a draw profile that arithmetic on idle
cycles already gives you, with uncertainty and interpretability. Revisit only if residual
analysis proves multi-zone stratification is the dominant error term. Keep the reference in
the file; do not build it.

## 6. The habit matrix as specified learns the wrong thing

A TimescaleDB continuous aggregate over *power consumption* is not a hot-water draw profile.
Power is control-dependent: once the optimiser shifts heating to cheap hours, the aggregate
reflects **your own scheduler's output**, not user behaviour. That is a feedback loop that
will converge on a self-confirming, wrong habit model.

Aggregate the *deduced draw energy* `D_k` — a separate derived series written by the
estimator — not raw power.

And a mean is insufficient for a chance constraint. Use TimescaleDB's `percentile_agg` /
tdigest hyperfunctions to keep quantiles per `(day_of_week, slot)`, so the optimiser can ask
for the p90 draw rather than the average.

## 7. Make the comfort constraint physical, not a flat 20 %

A fixed 20 % floor is an arbitrary robust margin: too loose for a family at 19:00, absurdly
tight for an empty flat at 03:00. In energy units the constraint has a real meaning:

```
E_k ≥ E_reserve(t) = p90 draw over the next 3 h,  floored at ~10 % of E_full
```

Litres × ΔT × 1.163 Wh/L/K gives the shower energy directly. Two wins:

- Fewer cold showers *and* more harvested flexibility than a flat buffer.
- The dashboard metric becomes **"showers remaining"** instead of an abstract percentage —
  legible to the user, and it makes the Boost button self-explanatory.

Note the 1R1C energy model is *conservatively* biased here: real tanks stratify during a
draw, preserving usable temperature at the top, so a well-mixed single-node model
under-estimates deliverable hot water. Erring safe on comfort is the right direction.

## 8. Cold-shower rate is currently unmeasurable — fix that in the pilot

Your primary risk metric has no observable. Without ground truth you cannot tell a
successful aggressive shed from a near-miss.

Instrument the first 10–20 pilot units with a €3 strap-on DS18B20 on the tank wall or outlet
pipe — **for validation only**, removed at scale. This is not a retreat from the sensorless
thesis; it is how you cheaply prove it. It gives you the labelled dataset to measure SoC MAE,
tune the interval observer, and (only if ever needed) train a PINN.

Add explicit in-app feedback ("was the water hot?") plus Boost-press as a proxy signal.
