# AquaCell

Aggregating residential electric water heaters into a virtual power plant for
Croatian grid balancing, using only a low-cost smart relay in series with the
heating element. No thermistor, no plumbing, no pilot wire. Telemetry is relay
state and active power; a virtual sensor reconstructs stored energy from that.

Start with [`docs/05-sinteza.md`](docs/05-sinteza.md). It is the plan of record
and supersedes the earlier documents wherever they conflict.

## What the simulation actually found

The original plan aimed at *reducing* consumption. Absorbing surplus energy
turns out to be the larger product, at lower risk, with no effect on comfort —
a customer whose tank was filled on command has a full tank.

```
night absorption   00-05    1.7 - 2.8 MW     ~2,400 devices per MW
solar absorption   10-16    1.0 - 1.6 MW
morning reduction  06-09    0.8 - 1.2 MW     ~7,000-8,000 devices per MW
evening reduction  17-21    0.7 - 1.1 MW
```

Figures are for a 5,000-device fleet. Three consequences:

- No symmetric all-day product. Flexibility varies by a factor of nine across
  the day, so bids must be tied to the hour.
- A fleet above ~1,000 devices does not get more reliable, only larger. The
  22-24 % haircut is correlated variance and is structural.
- Guarantees are not possible. Bids are probabilistic with an explicit risk
  level. The interval observer that produces hard bounds is the wrong tool for
  the market and is kept only to protect comfort.

These come from a simulator with **estimated** consumption profiles, not
measurements of Croatian households. Per-figure reliability is in
`docs/05-sinteza.md` §9.

## Repository layout

```
docs/                        Plan of record, reviews, decision register
scripts/                     Provisioning helpers, Shelly simulator
apps/
  simulator/                 Stratified tank + synthetic draws       BUILT
  core_engine/               Erlang/OTP real-time layer              POC
infrastructure/              EMQX, TimescaleDB, Redis configuration  CONFIGURED
edge_scripts/                Shelly mJS safety net                  WRITTEN, UNTESTED
docker-compose.yml           Local infrastructure
```

Directories for the Python scheduler, the Django API and the Next.js dashboard
do not exist yet. See the build order below for why, and
`docs/04-decision-register.md` §J for the decisions behind it.

To connect a real Shelly and control it by hand, see
[`docs/06-shelly-poc-runbook.md`](docs/06-shelly-poc-runbook.md). Read the
hardware warning at the top of it before wiring anything to a boiler.

## Build order

Phase 0, in this order (decision #76):

1. **`apps/simulator/`** — done. You cannot validate a virtual sensor on one
   flat, and this is what makes iteration take minutes instead of days.
2. **Interval observer + anchor detection**, validated against the simulator.
   Partly in `apps/simulator/aquacell_sim/estimator.py`.
3. **One Shelly + one €3 validation thermistor** in the Prečko flat. Confirm
   the anchors fire; measure real standing loss, `E_hyst`, `E_full`.
4. **HiGHS MILP scheduler** — `apps/scheduler/`, not created yet. A single
   Python process with APScheduler. No GEKKO, no Celery: decision #25 and #77.
5. **`edge_scripts/connection_fallback.js`** — written, needs hardware testing.
6. **`apps/core_engine/`** — skeleton exists. Shared subscriptions, gproc
   registry, state rehydration, ramp governor.

Deferred to Phase 1+: Django, Celery, the Next.js dashboard, TimescaleDB
continuous aggregate tuning, the particle filter.

Not being built on current evidence: PINNs, Fokker-Planck population control,
device-side PEM (decisions #17, #52, #78).

Blocked on external answers before Phase 1 (decision #79): whether certified
metering is mandatory; HOPS prequalification and telemetry rules; whether
Croatian residential dynamic-price contracts exist; which supplier carries the
balance-group position.

## Running the infrastructure

```bash
cp .env.example .env      # then edit: every changeme must change
docker compose up -d
docker compose ps         # all three should report healthy
```

- EMQX dashboard: http://127.0.0.1:18083
- Postgres: `127.0.0.1:5432`
- Redis: `127.0.0.1:6379`

The schema in `infrastructure/postgres/init_timescale.sql` is applied only on
first start. To re-apply, destroy the volume:
`docker compose down -v` — this deletes all local data.

## Running the simulator

See [`apps/simulator/README.md`](apps/simulator/README.md).

```bash
cd apps/simulator
pip install -r requirements.txt
pytest -m "not slow"
python3 -m aquacell_sim.run_year
```

## Building the Erlang core

Needs OTP 27 and rebar3, neither of which is required for the simulator. No C
toolchain is needed: `rebar.config.script` excludes `quicer`, the QUIC NIF that
`emqtt` would otherwise drag in. That exclusion is why `emqtt` is pinned to a
git tag rather than the Hex package — see the comments in `rebar.config`.

```bash
cd apps/core_engine
rebar3 compile
rebar3 shell        # boots an empty supervision tree
```

The tree is intentionally empty. `src/aquacell_sup.erl` documents the intended
children and, more importantly, the order they must start in — the ramp
governor comes up before anything that can dispatch.

## SECURITY

Read this before exposing anything.

- **`docker-compose.yml` is for local development only.** Every port is bound
  to `127.0.0.1`. The MQTT plaintext listener on 1883 is enabled and the TLS
  listener on 8883 uses the self-signed certificates shipped in the EMQX
  image with `verify = verify_none`. Neither is acceptable for a device on a
  real network.
- Before any device connects over the internet: disable the 1883 listener,
  install a real CA, and set `verify = verify_peer` with
  `fail_if_no_peer_cert = true` in `infrastructure/emqx/emqx.conf`.
  Decision #53.
- **Per-device credentials, never a shared password.** A homeowner can read
  their own Shelly configuration, so one extracted shared credential
  compromises the fleet.
- The ACL in `infrastructure/emqx/acl.conf` is default-deny and scopes each
  client to its own topic prefix. A bare `#` subscription is refused by name.
- **The ramp governor is not optional.** Synchronous control of this much load
  is a grid-scale capability and a regulator will ask about it. Decision #54
  puts a hard aggregate kW/min limit in Erlang on the last hop, so it still
  holds when the optimiser is wrong or compromised.
- No component here has authentication in front of it yet, including the EMQX
  dashboard beyond its default credentials. Do not put this on a public
  address as it stands.

## What has been verified

Checked on 2026-09-06, on OTP 27 in a container:

- `rebar3 compile` is clean with `warnings_as_errors`, and `rebar3 shell` boots
  `aquacell_sup` with zero children as intended. `quicer` is absent from the
  dependency tree. `rebar.lock` pins `emqtt` to a commit.
- `docker compose up` brings all three services to healthy.
- The schema applies: both hypertables, the `draw_hourly` continuous
  aggregate, the compression policy on `telemetry`, and `percentile_agg` from
  `timescaledb_toolkit`.
- Redis reports `appendonly yes`, `appendfsync everysec`,
  `maxmemory-policy noeviction`, and a Stream consumer-group round trip works.
- EMQX rejects anonymous connections. With a provisioned credential, a device
  can publish to its own topic, is **disconnected** when it tries another
  device's topic, and is refused a bare `#` subscription. `ws`, `wss` and
  `quic` listeners are confirmed off.
- The Shelly POC path works end to end against `scripts/fake_shelly.py`:
  `shelly_ctl:info/1`, `status/1`, `on/1`, `toggle/1` and `power/1` all
  round-trip over the RPC channel, and cached status arrives via `status_ntf`.
  A device attempting to forge RPC replies for another device, to command
  another device, or to use the `shellies/command` broadcast topic is
  disconnected in all three cases.

## Known gaps

- No hardware has been involved in any of the above. The POC was verified
  against a simulated Shelly only.
- `apps/simulator/requirements.txt` pins `numpy==2.1.3` and `pytest==8.3.4`.
  The tests were last run against numpy 1.26.4 and pytest 9.1.1 and passed;
  the pins have not been verified against a clean install.
- `edge_scripts/connection_fallback.js` has never run on hardware and is not
  installed by the POC runbook. It is written from the documented mJS API and
  nothing more.
- `aquacell_shelly` is a single wildcard subscriber, which decision #30
  rejects for the fleet, and there is no ramp governor (#54) in front of it.
  It is a bench tool.
- No CI, no linting, no migration tooling (decision #58).
- No Prometheus or Grafana (decision #57). A fleet without dashboards is
  unoperable.
- The KPI set is listed at the end of `docs/02-review-architecture.md` but is
  not implemented anywhere (decision #59).
