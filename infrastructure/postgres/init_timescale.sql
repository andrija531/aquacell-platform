-- AquaCell TimescaleDB schema.
--
-- Runs once, on first container start, from /docker-entrypoint-initdb.d.
-- To re-run it you must destroy the timescale-data volume.
--
-- This is Phase 0 scaffolding. It is deliberately narrow: it covers device
-- identity, twin rehydration, event telemetry, anchors, deduced draws, and
-- schedules. It does not attempt the Django-era tables.

CREATE EXTENSION IF NOT EXISTS timescaledb;
-- Provides percentile_agg, required by decision #19. Present in the
-- timescaledb-ha image; absent from plain timescale/timescaledb.
CREATE EXTENSION IF NOT EXISTS timescaledb_toolkit;


-- ===========================================================================
-- Device registry
-- ===========================================================================
CREATE TABLE device (
    device_id       text PRIMARY KEY,          -- Shelly MAC, also MQTT clientid
    installed_at    timestamptz NOT NULL DEFAULT now(),

    -- Nameplate. p_nom_w is what the element draws, not what the relay is
    -- rated to switch: decision #39 forbids switching the element with the
    -- Shelly relay at all, so a DIN contactor sits in between (#41).
    p_nom_w         integer NOT NULL,
    tank_litres     integer NOT NULL,

    -- Identified parameters, all in energy units. Decisions #1 and #7: the
    -- normalised-temperature SoC equation is dimensionally wrong, so state,
    -- constraints and UI are all kWh.
    e_full_wh       integer,                   -- decision #9, one measured deep reheat
    e_hyst_wh       integer,                   -- decision #6
    standing_loss_w real,                      -- decision #5, median over quiet nights

    -- Decision #10: `L` and e_full drift when the user turns the dial.
    -- Change-point detection writes here.
    params_updated_at timestamptz,

    -- Decision #10 / #5: standing loss needs a genuine absence period to
    -- measure, which a household may not produce for months. A device with
    -- an unreliable L must not sell absorption.
    loss_estimate_reliable boolean NOT NULL DEFAULT false,

    -- Decision #51: randomise dispatch within postal-code clusters so no
    -- single LV feeder receives a coordinated command. Coordinates, and
    -- PostGIS, only if substation mapping with the DSO ever materialises.
    postal_code     text,

    -- Decision #81: the electrician records the thermostat dial at >= 60 C at
    -- commissioning, otherwise a later cut-out cannot be claimed as proof of
    -- a disinfection temperature in a sensorless system.
    commissioned_setpoint_c real,

    -- Decision #24: a few pilot units carry a EUR 3 DS18B20 for validation
    -- only. Used to measure SoC MAE, removed at scale.
    has_validation_probe boolean NOT NULL DEFAULT false
);


-- ===========================================================================
-- Twin state, for rehydration
--
-- Decision #32: a node restart or deploy must not blank the fleet's stored
-- energy. The Erlang twin reads this on init/1 and checkpoints every few
-- minutes. If updated_at is older than TWIN_STALE_AFTER_S the state is
-- *unknown*, and the correct response is to fail safe — release the device to
-- its mechanical thermostat rather than act on a stale estimate.
-- ===========================================================================
CREATE TABLE device_state (
    device_id       text PRIMARY KEY REFERENCES device(device_id) ON DELETE CASCADE,
    updated_at      timestamptz NOT NULL,

    -- Interval observer bounds (decision #15). Not a point estimate: the
    -- system is hybrid with censored observations, so an EKF would
    -- misreport its own confidence, and safety margins derive from that
    -- confidence (decision #14, WONTDO).
    stored_wh_lo    real NOT NULL,
    stored_wh_hi    real NOT NULL,

    relay_commanded boolean NOT NULL,
    power_w         real,
    last_anchor_at  timestamptz,

    -- Decision #38: reject non-increasing generations so a replayed or
    -- out-of-order schedule cannot overwrite a newer plan.
    schedule_generation bigint NOT NULL DEFAULT 0,

    -- Decision #40: relay/contactor wear is a first-class constraint, and
    -- #42 puts a switching penalty in the MPC objective.
    switch_cycles   bigint NOT NULL DEFAULT 0
);


-- ===========================================================================
-- Telemetry
--
-- Report-on-change plus heartbeat (decision #35), NOT 5 s polling. At 50k
-- devices, 1 sample/5 s is 864M rows/day for a signal that is quasi-binary.
-- Report-on-change is ~2.5M rows/day and loses nothing, because every event
-- that matters is a change. Decision #36 allows bursting to 1 s inside
-- activation windows, where settlement needs the resolution.
-- ===========================================================================
CREATE TABLE telemetry (
    device_id       text NOT NULL,
    ts              timestamptz NOT NULL,
    power_w         real NOT NULL,
    relay_commanded boolean NOT NULL,
    -- 'change' | 'heartbeat' | 'burst' | 'probe' | 'reconnect'
    kind            text NOT NULL
);

SELECT create_hypertable('telemetry', 'ts', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX ON telemetry (device_id, ts DESC);

ALTER TABLE telemetry SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id',
    timescaledb.compress_orderby   = 'ts DESC'
);
SELECT add_compression_policy('telemetry', INTERVAL '7 days');


-- ===========================================================================
-- Anchor events
--
-- Error-triggered recalibration against the mechanical thermostat. The relay
-- is in series before the bimetallic thermostat, so P > 0 implies both are
-- closed.
--
-- Decision #8: treat the cut-out anchor as precise but BIASED. Decision #5 in
-- the correction log is blunter — "thermostat open means tank full" is simply
-- untrue: 145 violations in 45 days, worst case 1534 Wh, because the tank is
-- stratified and the probe averages over the lower half.
-- ===========================================================================
CREATE TABLE anchor_event (
    device_id       text NOT NULL REFERENCES device(device_id) ON DELETE CASCADE,
    ts              timestamptz NOT NULL,
    -- 'cutout'  : commanded ON, power 2000 -> 0, thermostat opened
    -- 'cutin'   : commanded ON, power 0 -> 2000, thermostat snapped closed
    kind            text NOT NULL,
    stored_wh_after real,
    PRIMARY KEY (device_id, ts, kind)
);


-- ===========================================================================
-- Deduced draw
--
-- Decision #18: aggregate the DEDUCED draw series, never raw power. If you
-- aggregate power, the habit model learns the optimiser's own schedule —
-- shift heating to 03:00, the aggregate shows heating at 03:00, and the model
-- concludes the user showers at 03:00. A self-confirming feedback loop.
-- ===========================================================================
CREATE TABLE deduced_draw (
    device_id       text NOT NULL,
    ts              timestamptz NOT NULL,
    wh              real NOT NULL,
    -- Decision, correction log 8.1: sizing draws by measured energy instead
    -- of the V x 1.163 x dT formula, which needs two unknowns.
    -- 'small' < 200 Wh | 'shower' 800-1600 Wh | 'bath' > 2500 Wh
    size_class      text,
    -- How the draw was inferred: reheat duration after a forced-OFF window,
    -- or a passive estimate between anchors.
    method          text NOT NULL
);

SELECT create_hypertable('deduced_draw', 'ts', chunk_time_interval => INTERVAL '7 days');
CREATE INDEX ON deduced_draw (device_id, ts DESC);


-- ---------------------------------------------------------------------------
-- Hourly draw distribution per device.
--
-- Decision #19: keep quantiles via percentile_agg, not means. The reserve
-- floor needs the upper tail — a mean gives a cold shower whenever anything
-- unusual happens.
--
-- Decision #20 consumes this: the floor is the p90 of draw over the next 3
-- hours, with a ~10 % E_full minimum, replacing a flat 20 % SoC buffer. A
-- fixed number is simultaneously too tight at 18:30 in a family home and
-- pointlessly wide at 03:00 in an empty flat.
-- ---------------------------------------------------------------------------
CREATE MATERIALIZED VIEW draw_hourly
WITH (timescaledb.continuous) AS
SELECT
    device_id,
    time_bucket(INTERVAL '1 hour', ts) AS bucket,
    percentile_agg(wh)                 AS wh_percentiles,
    sum(wh)                            AS wh_total,
    count(*)                           AS n_draws
FROM deduced_draw
GROUP BY device_id, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy('draw_hourly',
    start_offset     => INTERVAL '30 days',
    end_offset       => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');


-- ===========================================================================
-- Schedules
--
-- Written by the Python scheduler, consumed by Erlang off a Redis stream
-- (decision #37). Persisted here so a restart can recover the active plan
-- without waiting for the next solve.
--
-- Decision #29: tz-aware timestamps and a computed horizon length. A
-- hardcoded 96-slot array breaks on the 23- and 25-hour DST days.
-- ===========================================================================
CREATE TABLE schedule (
    device_id       text NOT NULL REFERENCES device(device_id) ON DELETE CASCADE,
    generation      bigint NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    horizon_start   timestamptz NOT NULL,
    slot_seconds    integer NOT NULL,
    -- One element per slot. Length is computed, not assumed.
    relay_plan      boolean[] NOT NULL,
    PRIMARY KEY (device_id, generation)
);


-- ===========================================================================
-- Dispatch audit
--
-- Decision #54: the ramp governor is enforced in Erlang on the last hop, and
-- refuses any dispatch exceeding the aggregate limit regardless of what the
-- optimiser asked for. Decision #55: signed commands with replay protection.
-- Both need an audit trail that records refusals, not just successes.
-- ===========================================================================
CREATE TABLE dispatch_audit (
    id              bigserial PRIMARY KEY,
    ts              timestamptz NOT NULL DEFAULT now(),
    -- 'schedule' | 'activation' | 'boost' | 'disinfection' | 'probe'
    reason          text NOT NULL,
    device_count    integer NOT NULL,
    delta_kw        real NOT NULL,
    -- false when the ramp governor refused it
    allowed         boolean NOT NULL,
    note            text
);
