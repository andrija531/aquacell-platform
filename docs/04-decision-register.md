# Decision Register

Stable IDs. Detail for each item lives in `01-review-estimation.md`, `02-review-architecture.md`,
`03-review-economics.md`. Do not renumber; append only.

Status codes: `OPEN` (not started) · `WIP` · `DONE` · `BLOCKED` (waiting on external answer) · `WONTDO`

## A. State estimation (1–24)

| # | Decision | Rejected alternative | Status |
|---|---|---|---|
| 1 | Track stored energy (kWh); the `α·SoC` loss term is physically wrong | Patch the normalised-temperature equation with ambient/inlet terms | OPEN |
| 2 | Estimate inlet temperature indirectly from seasonal drift in reheat energy | Seasonal lookup table (acceptable fallback); ignoring it (not acceptable) | OPEN |
| 3 | Hardcode `η = 1` for the resistive element and document the assumption | Try to identify `UA` and `C` separately from power data (impossible) | OPEN |
| 4 | Delete the SciPy/GEKKO cooling-curve fit | Keep the solver with heavier data filtering | OPEN |
| 5 | Standing loss `L = P_nom × D_on/(D_on+D_off)`, median over quiet nights | Solver-based estimation | OPEN |
| 6 | Hysteresis as energy `E_hyst = P_nom × D_on` | Estimate `ΔT_hyst` in kelvin | OPEN |
| 7 | All state, constraints and UI in kWh | Normalised temperature SoC | OPEN |
| 8 | Treat the cut-out anchor as precise but biased (probe height, tank geometry) | Treat cut-out as a genuinely full tank | OPEN |
| 9 | `E_full` = integrated power over one measured deep reheat | Assume `T_max` corresponds to SoC 1.0 | OPEN |
| 10 | Change-point detection on `E_hyst` to catch thermostat dial changes | Manual recalibration | OPEN |
| 11 | Bound shed length by worst-case draw *only where the observer has no lower bound* | Plan sheds on average historical draw | OPEN |
| 12 | 2–3 s active probe pulses during sheds | Remain blind while the relay is open | OPEN |
| 13 | Probe adaptively on uncertainty width, not on a timer | Fixed-interval probing | OPEN |
| 14 | No EKF — the system is hybrid with non-Gaussian, censored observations | Tune an EKF | WONTDO |
| 15 | Interval (set-membership) observer for MVP | Go straight to a Bayesian filter | OPEN |
| 16 | Particle filter later, in Python, at 1–5 min cadence | Run heavy filters inside Erlang | OPEN |
| 17 | No PINNs before stratification is proven to dominate residual error | Build PINNs in Phase 1 | WONTDO |
| 18 | Aggregate deduced draw `D_k`, never raw power | Continuous aggregate over power consumption | OPEN |
| 19 | Keep p90 quantiles via `percentile_agg`, not means | Mean draw per weekday-hour | OPEN |
| 20 | Time-varying floor = p90 draw over next 3 h, min ~10 % `E_full` | Flat 20 % SoC floor | OPEN |
| 21 | Surface "showers remaining" to the user | Abstract SoC percentage | OPEN |
| 22 | Rely on single-node pessimism during drawdown as a safety margin | Build a multi-node stratification model | OPEN |
| 23 | Create explicit cold-shower observables: in-app feedback + Boost presses | Wait for complaints | OPEN |
| 24 | €3 DS18B20 on 10–20 pilot units, validation only, removed at scale | Fully sensorless from day one | OPEN |

## B. Optimisation and control (25–29)

| # | Decision | Rejected alternative | Status |
|---|---|---|---|
| 25 | HiGHS or OR-Tools MILP | GEKKO / APOPT MINLP | OPEN |
| 26 | Local solving only (`remote=False` if GEKKO survives anywhere) | GEKKO default remote solve on a public server | OPEN |
| 27 | Rolling re-solve every 15 min, plus after every activation and anchor | Single daily 14:15 batch | OPEN |
| 28 | One objective: arbitrage + capacity − activation cost − comfort penalty | Separate arbitrage and balancing systems | OPEN |
| 29 | Timezone-aware timestamps, computed horizon length | Hardcoded 96-slot array | OPEN |

## C. Erlang / real-time (30–38)

| # | Decision | Rejected alternative | Status |
|---|---|---|---|
| 30 | EMQX shared subscriptions, N shards, hash device→shard | Single wildcard subscriber process | OPEN |
| 31 | `gproc` or ETS registry for twins | `list_to_atom(Mac)` | OPEN |
| 32 | Rehydrate on `init/1`; checkpoint every few min; stale ⇒ fail safe | Start from zero after deploys | OPEN |
| 33 | Shard `db_batcher`; separate telemetry and command paths; `COPY` | One batcher, one queue, multi-row INSERT | OPEN |
| 34 | `pgo` only | Both `pgo` and `epgsql` | OPEN |
| 35 | Report-on-change + heartbeat | 5 s polling | OPEN |
| 36 | Burst to 1 s during activation windows only | Constant high resolution | OPEN |
| 37 | Redis Streams with consumer groups | Redis Pub/Sub | OPEN |
| 38 | Monotonic `schedule_generation`; reject non-increasing | Accept every message | OPEN |

## D. Hardware and edge safety (39–47)

| # | Decision | Rejected alternative | Status |
|---|---|---|---|
| 39 | Do not switch the element with the Shelly relay (2000 W switching limit) | Switch up to 16 A directly | OPEN |
| 40 | Track cumulative switch cycles per device | Ignore relay wear | OPEN |
| 41 | Shelly drives a €10–15 DIN modular contactor | Replace failed Shellys in the field | OPEN |
| 42 | Switch-count penalty in the MPC objective | Unlimited switching | OPEN |
| 43 | Fail to ON on connectivity loss | Fail to OFF | OPEN |
| 44 | Treat naive fail-ON as a correlated fleet event and a delivery risk | Ignore herd risk from the safety path | OPEN |
| 45 | Randomised 0–300 s fallback delay computed on the device | Server-side staggering | OPEN |
| 46 | Derate bids using the correlated connectivity-loss distribution | Assume independent 99 % uptime | OPEN |
| 47 | Power-on default ON + built-in schedule as third fallback | Rely only on the mJS script | OPEN |

## E. Fleet-level grid effects (48–52)

| # | Decision | Rejected alternative | Status |
|---|---|---|---|
| 48 | Separate voltage-step mitigation from thermal-loading mitigation | Assume 60 s jitter solves both | OPEN |
| 49 | Wave release over 30–60 min, ranked by stored energy, jitter within waves | Instant release | OPEN |
| 50 | Design to a recomputed rebound (~20–40 % of fleet), not nameplate | Design to 100 MW | OPEN |
| 51 | Randomise within postal-code clusters | Randomise across the whole fleet | OPEN |
| 52 | Server-side randomised admission | Device-side PEM | WONTDO |

## F. Security (53–55)

| # | Decision | Rejected alternative | Status |
|---|---|---|---|
| 53 | Per-device credentials, mTLS where provisioning allows, TLS 8883, per-topic ACLs | Shared MQTT password | OPEN |
| 54 | Aggregate MW/min ramp governor enforced in Erlang, last hop | Limit only in the Python optimiser | OPEN |
| 55 | Signed commands with replay protection; confirmation above a size threshold | Auto-dispatch everything | OPEN |

## G. Missing components (56–59)

| # | Decision | Rejected alternative | Status |
|---|---|---|---|
| 56 | Build the stratified tank simulator + DHWcalc/EN 16147 draws first | Test only on the real flat | OPEN |
| 57 | Prometheus + Grafana + alerting | Operate without telemetry dashboards | OPEN |
| 58 | CI, linting, migrations | Manual deploys | OPEN |
| 59 | Define the KPI set before writing the estimator | Add metrics later | OPEN |

## H. Economics (60–67)

| # | Decision | Rejected alternative | Status |
|---|---|---|---|
| 60 | Size on ~12 % duty cycle (≈12 MW naive shed at 50 k units) | Assume nameplate capacity | OPEN |
| 61 | Price the opportunity cost of holding reserve; plan on 10–20 % symmetric | Treat reserve availability as free | OPEN |
| 62 | Treat ~5 000 units as the floor for independent 1 MW bidding | Treat 5 000 as comfortable scale | OPEN |
| 63 | No revenue in the Phase 1 column | Forecast revenue from 100 units | OPEN |
| 64 | Replace €40–150/device/yr with actual HOPS clearing prices | Rely on theoretical spreads | BLOCKED |
| 65 | Attack install cost via EWH-replacement bundling and installer channels | Accept a €60 standalone install | OPEN |
| 66 | Verify residential dynamic-tariff availability before B2C messaging | Pitch day-ahead savings | BLOCKED |
| 67 | B2C offer = free hardware + fixed annual payment + hot-water guarantee | Pitch bill savings | OPEN |

## I. Regulation (68–74)

| # | Decision | Rejected alternative | Status |
|---|---|---|---|
| 68 | Establish in writing whether certified metering is required | Assume Shelly telemetry is admissible | BLOCKED |
| 69 | Obtain HOPS prequalification/telemetry rules before ordering Phase 1 hardware | Build first | BLOCKED |
| 70 | Target mFRR (12.5 min, MARI) first | Target aFRR (5 min, PICASSO) first | OPEN |
| 71 | Fraction-of-population switching to follow continuous signals | Toggle the whole fleet | OPEN |
| 72 | Secure a BRP/supplier agreement for shifted energy | Ignore imbalance settlement | BLOCKED |
| 73 | Consent, comfort SLA, always-wins Boost override | Launch without terms | OPEN |
| 74 | Weekly ≥60 °C / ≥30 min disinfection as a hard MPC constraint | Ignore hygiene | OPEN |

## J. Sequencing (75–79)

| # | Decision | Rejected alternative | Status |
|---|---|---|---|
| 75 | Build the Erlang core early — it shapes everything above it | Defer Erlang | OPEN |
| 76 | Phase 0 order: simulator → observer → 1 instrumented Shelly → MILP → mJS → Erlang | Start with the dashboard | OPEN |
| 77 | Defer Django, Celery, Next.js, particle filter | Build the full stack now | OPEN |
| 78 | Discard PINNs, Fokker–Planck, device-side PEM | Build the academic features | WONTDO |
| 79 | Answer the four regulatory/economic questions before Phase 1 | Guess | BLOCKED |

## K. Added after review of the decision list (80–83)

| # | Decision | Rejected alternative | Status |
|---|---|---|---|
| 80 | Sell flexibility into an existing BSP's portfolio before self-prequalifying — removes the 1 MW floor and the certified-metering question from the critical path | Self-prequalify with HOPS as the only route to revenue | OPEN |
| 81 | Commissioning step: electrician sets and records the mechanical thermostat at ≥60 °C, so a later cut-out event is *provable* ≥60 °C — without it, disinfection (74) is unverifiable in a sensorless system | Assume the dial is high enough | OPEN |
| 82 | Inlet temperature affects the volume→energy *forecast* mapping, not the state update, once draws are measured in kWh — do not model it twice | Add inlet temperature to the state equation as well | OPEN |
| 83 | Audit total conservatism end to end (11 + 20 + 22 + 46 + 50 + 61) before launch; stacked independent safety margins can erase all sellable flexibility | Tune each margin in isolation | OPEN |
