# AquaCell — Source Brief (as provided, 2026-08-29)

Canonical record of the original research report and master plan that seeded this project.
Kept verbatim in substance so later reviews can trace which claims were original vs. revised.
See `01-technical-review.md` for the critical review and the revised plan of record.

## Thesis

Aggregate residential Electric Water Heaters (EWHs) into a VPP for grid balancing
(aFRR/mFRR) and day-ahead arbitrage, using **only** a low-cost smart relay in series
with the heater (Shelly 1PM Gen3). No thermistor, no plumbing, no pilot wire.
Telemetry is limited to: relay state `R ∈ {0,1}` and active power `P_t` (W).

A "virtual sensor" reconstructs thermal State of Charge from that sparse signal.

## Claimed algorithmic stack

1. **1R1C grey-box thermal model**

   `C dT/dt = Q_heat − ṁ·Cp·(T_tank − T_inlet) − UA·(T_tank − T_amb)`

   2R2C / PDE models capture stratification (thermocline) but 1R1C + a state
   observer is claimed to be the best efficiency/accuracy trade-off at fleet scale.

2. **SoC definition** `SoC = (T_tank − T_min) / (T_max − T_min)`
   with recursive update `SoC_{k+1} = α·SoC_k + β·P_k − γ·D_k − L_k`

3. **Error-Triggered Recalibration** against the mechanical thermostat.
   Relay is in series *before* the bimetallic thermostat, so `P > 0 ⟺ (R=1 ∧ M=1)`.
   - Upper anchor: commanded ON, power drops 2000 W → 0 W ⇒ thermostat opened ⇒ set `SoC = 1.0`, reset EKF covariance.
   - Lower anchor: commanded ON, power 0 W → 2000 W ⇒ thermostat snapped closed ⇒ set `SoC = (T_max − ΔT_hyst − T_min)/(T_max − T_min)`.
   - Hidden-draw deduction: after a forced-OFF period, measure reheat duration
     `Δt_heat` to cut-out, `E_missing = Δt_heat · P_nom`, subtract expected standing
     losses ⇒ retroactively infer user draw `D_k`.

4. **Demand prediction**: Conditional Hidden Semi-Markov Models (CHSMM) and LSTMs
   trained on the deduced `D_k` series; feeds Model Predictive Control.

5. **Physics-Informed Neural Networks** (recursive unsupervised PINN, power data only)
   as the state-of-the-art option for multi-zone modelling.

6. **Chance-Constrained MPC** to bound "cold shower risk":
   `P(SoC_{t+k} ≥ SoC_min) ≥ 1 − ε`, ε ≈ 0.01.
   Covariance growth without an anchor triggers a preemptive forced heat-to-full to
   re-anchor.

7. **Fleet desynchronisation** against the Thundering Herd / rebound peak:
   State Queueing by SoC priority, Packetized Energy Management (PEM),
   Fokker–Planck population models.

Cited prior art: Kepplinger (one-node grey-box + kNN usage prediction, ~6% MAPE),
Ruelens (DRL/LSTM control of TCLs from sparse observations), Xu et al. (PDE baseline),
Shen / Pandiyan / Gros (PINN multi-zone EWH).

## Competitor framing

| Player | Approach | Hardware |
|---|---|---|
| Voltalis (FR) | Residential DR on heating/EWH | Intrusive, pilot-wire / thermostat-boundary dependent |
| Tiko (CH, ENGIE) | 100k+ device VPP, FCR/aFRR to Swissgrid | Proprietary K-Box meter + M-Box gateway |
| Tibber (NO) | Supplier-side DA arbitrage | Asset-light, integrates factory sensors / generic relays |
| "Sensorless" startups | PINN + error-triggered recalibration | Generic €15 relay, 15-min install |

Claimed CapEx reduction: €150–300 → €15.

## Business model

- **B2C**: lower bills via CROPEX day-ahead arbitrage, guaranteed comfort, 15-min install.
- **B2B**: asymmetric aFRR/mFRR capacity sold to HOPS.
- Revenue: balancing (primary), arbitrage spread-sharing (secondary).
- GTM: Phase 0 = 1 unit (studio flat, Prečko); Phase 1 = 100 friendlies; Phase 2 = 5,000+ and real HOPS tenders.

## Proposed architecture

- **Edge**: Shelly 1PM Gen3 + local mJS script, MQTT heartbeat watchdog → force relay ON on connectivity loss (fall back to mechanical thermostat).
- **Ingestion**: EMQX broker; Redis Streams as the Python→Erlang bus.
- **Real-time (Erlang/OTP)**: `mqtt_router`, per-device `boiler_genserver` digital twins
  (holds SoC, catches the 0 W drop, applies `rand:uniform` jitter), `db_batcher`,
  `schedule_consumer` (XREADGROUP).
- **Storage**: PostgreSQL + TimescaleDB hypertables; continuous aggregates hold the
  2D (day-of-week × hour) habit matrix.
- **Brain (Python/Django/Celery)**: weekly `thermal_model.py` night-cooling SciPy fit;
  daily 14:15 `solver.py` GEKKO MPC over CROPEX prices with a hard 20% SoC floor;
  output = binary schedule JSON pushed to Redis.
- **Frontend**: Next.js dashboard — savings, Boost, Vacation, SoC buffer setting.

## Proposed monorepo layout

```
aquacell-platform/
├── docker-compose.yml
├── .env.example
├── infrastructure/{emqx,postgres,redis}/
├── edge_scripts/connection_fallback.mjs
└── apps/
    ├── core_engine/          # Erlang: aquacell_app, mqtt_router,
    │                         #   boiler_genserver, db_batcher, schedule_consumer
    ├── api_service/          # Django: optimization/{tasks,solver,thermal_model}.py, core/
    └── web_dashboard/        # Next.js
```

## Pipeline (as originally specified)

1. Sunday 05:00 — Celery fits heat-loss coefficient from the night cooling curve.
2. Continuously — TimescaleDB continuous aggregate maintains the habit matrix.
3. Daily 14:15 — Celery pulls CROPEX prices, GEKKO solves the binary schedule.
4. `XADD` schedule JSON to Redis Streams.
5. Erlang `schedule_consumer` → `boiler_genserver` applies ms jitter, `erlang:send_after`.
6. Erlang catches 2000 W → 0 W and hard-resets `SoC = 1.0`.
