# Technical Review, Part 3 — Economics, Regulation, Sequencing

This is where the plan is weakest. The engineering thesis is defensible; the business case
rests on three assumptions that are not yet tested, and one of them looks wrong.

## 1. The duty-cycle ceiling — the number the plan is missing

An EWH's average power is set by hot water use, not by its element rating.

For an 80 L tank, 2 kW element, two-person household:

| Quantity | Value |
|---|---|
| Usable stored energy (80 L × 40 K × 1.163 Wh/L/K) | ~3.7 kWh |
| Daily draw (100 L at ΔT 40 K) | ~4.65 kWh |
| Standing loss (ErP class C) | ~1.2 kWh/day |
| Total | ~5.9 kWh/day → **~245 W average** |
| Duty cycle on a 2 kW element | **~12 %** |

At any random instant only ~12 % of the fleet is drawing power. So 50 k units = 100 MW
nameplate but only **~12 MW of naive sheddable load**.

Control improves on that — you can pre-charge so more of the fleet is heating when a shed is
wanted — but not without limit, and holding reserve capacity has an opportunity cost:
upward reserve (absorbing surplus) requires tanks kept *deliberately empty*, which eats the
comfort margin and directly raises cold-shower risk. Downward reserve requires tanks kept
heating. You cannot hold both at once on the same device.

Practical planning figure: **reliable symmetric capacity ≈ 10–20 % of nameplate.**

Consequence for sizing: 1 MW *continuously available* aFRR needs roughly 7–10 MW nameplate,
i.e. **3 500–5 000 heaters** — which happens to be exactly the Phase 2 target. That is the
right target for the wrong reason: it is the *minimum viable* fleet for a single standard
product, not a comfortable scale. Phase 1's 100 units cannot bid into anything; treat Phase 1
purely as an algorithm-validation exercise and do not put revenue in that column.

## 2. Revenue per device — order of magnitude

Rough, and every input needs verification against actual HOPS tender results:

- **Capacity**: ~0.2 kW reliable × 8 h/day × ~10–40 €/MW/h → roughly **€25–150/device/year gross**, with aFRR at the top of that range and much stricter availability obligations.
- **Day-ahead arbitrage**: ~5 kWh/day shifted against a capturable spread of ~40 €/MWh → ~€70/year theoretical, realistically **€20–40/year** after imperfect forecasts.

Call it **€40–150/device/year gross**. Against that: ~€30 hardware, €40–80 electrician,
€10–20/year platform + connectivity + support, plus acquisition cost.

The unit economics work, but the margin is thin and depends entirely on prequalification,
low churn, and near-zero support cost per device.

### The CapEx lever is the wrong one

Note what the table above says: once you remove the €150 sensor, **the electrician becomes
the dominant CapEx item.** Optimising €150 → €15 of hardware while leaving a €60 install is
solving the second-order problem. The real lever is removing the electrician:

- Point-of-sale bundling at EWH replacement (the electrician is already there and already paid).
- Utility / installer channel partnerships.
- Reusing the existing night-tariff contactor position in the distribution board.

Croatian bathroom EWHs are typically hardwired, so a plug-in form factor is not available.
Plan the channel accordingly.

## 3. The B2C value proposition probably does not exist as written

"Reduced electricity bills through day-ahead arbitrage" requires the household to face
day-ahead prices. Croatian residential customers are largely on regulated/universal-service
tariffs with two-tariff (HT/LT day-night) meters. On such a tariff:

- The day-ahead price signal does not reach the customer at all.
- Night-tariff arbitrage is *already* captured by the legacy night contactor. You are competing with a mechanical timer that is free and works.

So arbitrage savings accrue to whoever holds the imbalance position — a supplier — not the
household. I could not confirm the current availability of dynamic-price residential
contracts in Croatia; that is a specific question for HERA and for HEP Elektra, and it should
be answered before any B2C messaging is written.

**The honest B2C pitch is a share of balancing revenue** — free hardware plus a fixed annual
payment, framed as "we pay you for permission to shift your water heating, and guarantee your
hot water." That is verifiable, does not depend on tariff reform, and is far less likely to
produce an angry customer comparing their bill year over year.

## 4. Prequalification and M&V is the real gate, not the algorithm

This is the largest single risk to the sensorless thesis, and the report does not mention it.

Balancing products require the BSP to *prove* delivery. For the European standard products,
full activation is **5 minutes for aFRR (PICASSO)** and **12.5 minutes for mFRR (MARI)** —
note the master plan says 15 min for mFRR, which is the wrong figure to design to. aFRR also
requires continuous tracking of a setpoint refreshed every few seconds. Minimum standard
product bid size is 1 MW.

A binary device cannot follow a continuous signal, but a *fleet* can, via
fraction-of-population switching — that part is fine, and it is how Tiko operates. Your power
telemetry is actually an asset here: you measure the real baseline per device, which is
exactly what an M&V regime demands.

The problem is *admissibility* of that measurement:

- A Shelly is not a certified meter, its timestamps are not NTP-grade, and its telemetry traverses consumer Wi-Fi and the public internet with loss.
- TSOs generally require baselines from the fiscal meter or from approved measurement equipment, at resolutions down to seconds for aFRR.

**Tiko's K-Box exists precisely because of this requirement.** If HOPS requires certified
sub-metering, the €15-versus-€150 argument is moot — you will install approved hardware or
you will not be prequalified. That single question determines whether the architecture is a
business or a hobby, and it costs one meeting to answer.

Recommended sequencing: get HOPS's prequalification, telemetry, and aggregator rules in
writing **before** Phase 1 hardware is ordered. Design Phase 2 around **mFRR first** — 12.5
minutes and a coarser M&V regime is far more forgiving of consumer-grade telemetry than
aFRR's seconds-resolution setpoint tracking. The plan has this backwards in emphasis.

Adjacent workstreams that are usually underestimated:

- **Imbalance settlement.** Shifted energy sits in a supplier's balance group. Independent aggregator activation triggers BSP↔BRP correction mechanisms under EU 2019/944 Art. 17 and the Croatian implementation. This needs a contract with a supplier, or you become one.
- **Consent and contract.** Explicit consent for load control, a comfort SLA, and an override (Boost) that always wins. Churn is the dominant business risk and one cold shower buys a cancellation.

## 5. Legionella — an unmanaged liability

Nowhere in the plan. Holding a tank at reduced SoC for extended periods parks the water in
the ~30–45 °C Legionella growth band, and your optimiser's entire purpose is to hold tanks
lower than they would otherwise sit. You are systematically creating the risk condition,
across thousands of tanks, on purpose, for profit.

Add a **hard, non-negotiable MPC constraint**: a periodic thermal disinfection cycle
(≥60 °C sustained ~30 min, at least weekly), scheduled into the cheapest available hours.
It costs little — you were going to heat to cut-out for re-anchoring anyway (Part 1, §3), so
the two requirements largely satisfy each other. Document it. It is also a *sales* asset:
"we manage your tank's hygiene cycle" is a better story than silence.

## 6. Revised sequencing

The stack as specified — Erlang + EMQX + Redis Streams + TimescaleDB + Django + Celery +
GEKKO + Next.js — is correct for 50 k devices and absurd for one flat in Prečko. But Erlang
is also the hardest layer to retrofit, so it should not be deferred.

**Phase 0, in this order:**

1. `apps/simulator/` — stratified tank + synthetic draw profiles. Build this *first*; it is how you test everything else without waiting for real days to pass.
2. Interval observer + anchor detection, validated against the simulator.
3. One Shelly + one €3 validation thermistor in the Prečko flat. Confirm the anchors fire, measure real `L`, `E_hyst`, `E_full`.
4. HiGHS MILP scheduler. No GEKKO, no Celery yet — a single Python process with APScheduler is sufficient and removes two components.
5. mJS fallback script *with randomised delay*.
6. Erlang core with shared subscriptions, gproc registry, state rehydration, and the ramp governor.

**Defer to Phase 1+:** Django/Celery, Next.js dashboard, TimescaleDB continuous aggregates
(a plain query is fine at 100 devices), particle filter.

**Never build (on current evidence):** PINNs, Fokker–Planck population control, device-side PEM.

**Answer before Phase 1:** HOPS telemetry and prequalification requirements; whether a
certified meter is mandatory; whether Croatian residential dynamic-price contracts exist;
which supplier will carry the balance-group position.
