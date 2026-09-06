# Technical Review, Part 2 — Architecture, Hardware, Safety

## 1. Replace GEKKO with a MILP solver

The problem is `min Σ price_k · P · u_k` subject to linear energy dynamics
`E_{k+1} = E_k + ηPΔt − LΔt − D_k`, bounds `E_reserve ≤ E_k ≤ E_full`, `u_k ∈ {0,1}`.
96 binaries, all constraints linear. That is a textbook MILP, not an MINLP.

- HiGHS (via `highspy`) or OR-Tools CBC solves it in single-digit milliseconds. MIT/Apache licensed, in-process.
- GEKKO would route it through APOPT as an MINLP: orders of magnitude slower and less robust.
- **`GEKKO()` defaults to `remote=True`**, which posts your model to a public APMonitor
  server. That is an outbound data path and a hard runtime dependency on a third party.
  If GEKKO is kept for any reason, `remote=False` is mandatory — plus local solver binaries.

Scaling argument: 50 k daily solves at 10 ms ≈ 500 s single-threaded, ~1 min across 8 cores.
The same workload in GEKKO plausibly overruns the daily window.

## 2. A daily 14:15 batch is day-ahead scheduling, not MPC

MPC means a rolling horizon that re-solves on new information. As specified, nothing
re-optimises after a balancing activation — yet an activation is precisely the event that
invalidates the plan, because the deferred energy must be repaid and the repayment collides
with the arbitrage schedule.

Two systems currently fight each other: Python owns the day-ahead plan, Erlang owns
real-time overrides, and no one reconciles them.

- Re-solve every 15 min on a shrinking-horizon basis, or at minimum immediately after every activation and every anchor event.
- Co-optimise one objective: arbitrage value + reserve capacity value − activation cost − comfort penalty. Not two independent optimisers.
- 14:15 itself is fine (SDAC gate closure is 12:00 CET, results ~12:45–13:00). But **DST will break a hardcoded 96-slot array** on the 23- and 25-hour days. Use tz-aware timestamps and a variable horizon length.

## 3. Erlang: four concrete failure modes

**Single wildcard subscriber is a bottleneck and a SPOF.** One `emqtt` process consuming
`aquacell/+/status` for 50 k devices funnels every message through one mailbox — it will
queue and OOM on a reconnect storm. Use EMQX **shared subscriptions**
(`$share/ingest/aquacell/+/status`) with N subscriber processes so the broker load-balances,
and hash device → shard for ordering.

**Never `list_to_atom(Mac)`.** Dynamic atoms are never garbage collected; the default limit
is ~1 M and you will leak toward it. Register twins via `{via, gproc, {n,l,{boiler,Mac}}}`
or an ETS-backed registry.

**GenServer state is lost on restart or deploy.** A node restart must not blank the fleet's
SoC. Rehydrate from Postgres on `init/1` (last known energy + timestamp), and define a
stale-state policy: if the last update is older than some threshold, the state is *unknown*,
so fail safe — release the device to its mechanical thermostat rather than acting on a stale
estimate. Checkpoint every few minutes.

**One `db_batcher` is a bottleneck with an unbounded mailbox.** Shard by device, use bounded
buffers, and drop-oldest on telemetry under backpressure. Telemetry is expendable; commands
are not — never share a queue between them. Use `COPY` rather than multi-row `INSERT`.

Also: `rebar.config` lists both `pgo` and `epgsql`. Pick one — `pgo` if you want pooling
built in.

## 4. Telemetry volume: the plan is ~100× oversized

50 k devices × 1 sample / 5 s = 10 k rows/s = **864 M rows/day**, tens of GB/day raw. That
dominates your infrastructure cost for no benefit, because the signal is quasi-binary
(0 W or ~2000 W).

Switch to **report-on-change plus heartbeat**: ~20–50 events/device/day → ~2.5 M rows/day at
50 k devices. Two orders of magnitude cheaper, and you lose nothing, because every event that
matters *is* a change.

Then make the rate **adaptive**: burst to 1 s resolution during activation windows, where
high-resolution evidence is needed for settlement. Set TimescaleDB `chunk_time_interval` to
1 day and enable compression after ~7 days.

## 5. Redis: Streams, not Pub/Sub

Part 1 of the plan says Streams (`XADD`/`XREADGROUP`); Part 2 says Pub/Sub. Streams is
correct — Pub/Sub silently drops schedules when the consumer is down.

Add a monotonic `schedule_generation` per device so a replayed or out-of-order message
cannot overwrite a newer plan. Consumer must be idempotent.

Worth questioning whether Redis is needed at all: schedules could live in Postgres with
`LISTEN/NOTIFY`, removing a component. Streams is defensible for the replay log; just do not
run both buses.

## 6. Hardware: do not switch the load with the Shelly relay

Shelly 1PM Gen3 is rated 16 A resistive but **2000 W max switching power at 240 VAC**. A
2 kW element at 230 V sits *at* that limit, and 3 kW elements — common enough — exceed it.
Relay endurance for this class of device is typically quoted in the 10⁴–10⁵ cycle range at
rated resistive load (verify against the vendor datasheet; I did not confirm a figure).

Do the arithmetic: a 15-minute probe cadence is 96 cycles/day ≈ 35 k/year. Add scheduling
switches and you burn through the contact rating in ~2 years. Fleet-wide relay failure means
truck rolls, which is the one cost that actually destroys the CapEx thesis.

Fix: **the Shelly drives a DIN modular contactor** (~€10–15, designed for 10⁵–10⁶ operations)
which switches the element. Total BOM ~€30 instead of €15 — still an order of magnitude below
a K-Box, and it converts a wear-out failure mode into a non-issue. Many Croatian installs
already have a night-tariff contactor in the board that you may be able to reuse.

Then treat switch count as a first-class constraint: track cumulative operations per device
and add a small switching penalty to the MPC objective.

## 7. Fail-safe ON is right, but naive fail-safe is a synchronised event

Defaulting to ON when MQTT drops is the correct instinct — the mechanical thermostat is a
perfectly good fallback and the customer never notices.

The problem is **correlated failure**. An EMQX restart, a Hetzner network blip, or a single
Croatian ISP outage drops thousands of devices at once. Two simultaneous consequences:

1. Your contracted shed silently evaporates mid-activation → non-delivery penalties.
2. Every affected device fails ON at the same instant → exactly the thundering herd you built Phase 5 to prevent, triggered by your own safety net.

Required:
- **Randomise the fallback delay in the mJS script** (per-device random 0–300 s), and jitter reconnect backoff. The safety net must desynchronise itself, at the edge, with no server involvement.
- Set the watchdog timeout long enough (10–15 min) to ride out a broker restart.
- Treat "no heartbeat" as "assume failed ON" in real-time available-capacity accounting, and derate bids by the measured connectivity-loss distribution — including its correlation structure, not just its mean.
- Belt and braces at the hardware level: power-on default state ON, plus a Shelly built-in schedule as a third net. mJS scripts have very limited RAM and can crash; ensure auto-restart on boot.

## 8. 60 s of jitter does not solve the rebound peak

Two distinct problems are being conflated.

- **Voltage step / inrush** on an LV feeder — milliseconds to seconds. Jitter across 60 s genuinely helps here, converting a 20 kW step on a feeder into a ramp.
- **Transformer thermal loading** — minutes to hours. Jitter over 60 s is a rounding error. The recovery *energy* is fixed: every kWh deferred must be repaid. Spreading the leading edge over a minute does nothing to the plateau that follows.

Reducing the rebound peak requires spreading recovery over **tens of minutes**: release in
waves prioritised by remaining energy (the report's State Queueing idea is right, its
timescale is off by two orders of magnitude), with a controlled aggregate power trajectory.

Also check the premise: "50 k × 2 kW = 100 MW shock" assumes every device fires. Only those
below the thermostat reclose point do. At a ~12 % duty cycle, a one-hour shed realistically
leaves 20–40 % ready to fire — 20–40 MW. Still serious, but the correct number to design to.

Grid-topology awareness is the harder gap: 20 heaters on one distribution transformer matter
far more than 50 k spread nationally, and you do not know the topology. Proxy by clustering
on postal code / coordinates and randomising *within* each cluster, so no single feeder ever
receives a coordinated command. Pursue substation mapping with the DSO when it becomes
material.

PEM as described is architecturally inconsistent with this design: it requires the SoC
estimate to live on the device, and your edge is a dumb relay. Server-side randomised
admission is mathematically equivalent and far simpler. Fokker–Planck population control is
irrelevant below ~10 k units.

## 9. Security: this fleet is a grid weapon

Synchronous control of 100 MW of load is a national-infrastructure-grade capability, and a
regulator will ask about it. Baseline controls:

- **Per-device credentials**, never a shared username/password. Homeowners can read their own Shelly config; one extracted shared credential compromises the fleet. mTLS client certificates if the provisioning flow can carry it. TLS on 8883, `allow_anonymous = false`, ACLs scoping each client to its own topic prefix.
- **A server-side ramp governor in Erlang, not Python.** A hard limit on aggregate MW of state change per minute, enforced on the last hop, that refuses to execute any dispatch exceeding it regardless of what the optimiser or an attacker asked for. This is the control that survives a compromised brain.
- Signed commands with replay protection; human confirmation for dispatches above a threshold.
- Per-device jitter is a structural mitigation here too, not just a grid-friendliness feature.

## 10. Missing from the repo layout

- **`apps/simulator/`** — the most important omission. You cannot validate a virtual sensor on one flat. Build a stratified multi-node tank model plus synthetic draw profiles (DHWcalc / EN 16147 tapping cycles), generate ground truth, and measure estimator SoC MAE and cold-shower rate offline. This is what lets you iterate in minutes instead of days, and it should exist *before* the estimator.
- **Observability** — Prometheus/Grafana, per-device state, alerting. A fleet without dashboards is unoperable.
- **CI, linting, migrations.**
- A dispatch service separated from the optimiser.
- `connection_fallback.mjs` — Shelly scripting is mJS, conventionally `.js`. Cosmetic.

## KPIs to define now

SoC MAE against instrumented pilot units · cold-shower events per 1 000 device-days ·
distribution of time-between-anchors · fraction of fleet-time in high-uncertainty state ·
delivered vs. bid capacity · relay/contactor cycles per device · telemetry loss rate ·
mean and correlation structure of fallback events.
