%%%-------------------------------------------------------------------
%%% @doc Root supervisor.
%%%
%%% The tree is empty on purpose. Nothing below is implemented yet, and an
%%% empty module named after a decision is worse than no module at all: it
%%% looks implemented in a directory listing and invites someone to fill it in
%%% without re-reading why it exists. So the roadmap lives here, in comments,
%%% next to the start order it has to respect.
%%%
%%% Intended children, in start order:
%%%
%%%   1. aquacell_db_sup
%%%      pgo pool. Everything else needs it, so it starts first.
%%%      Decision #33: shard the batcher by device, bound the buffers, and
%%%      drop-oldest on telemetry under backpressure. One db_batcher with an
%%%      unbounded mailbox is a bottleneck that fails by growing until the
%%%      node dies. Telemetry is expendable, commands are not, so they never
%%%      share a queue. Bulk load with COPY, not multi-row INSERT.
%%%
%%%   2. aquacell_ramp_governor
%%%      Decision #54. A hard ceiling on aggregate kW of state change per
%%%      minute, enforced here on the last hop, that refuses any dispatch
%%%      exceeding it regardless of what the optimiser asked for.
%%%
%%%      This starts BEFORE anything that can dispatch. Synchronous control of
%%%      this much load is a national-infrastructure-grade capability, and the
%%%      governor is the one control that still holds if the Python brain is
%%%      compromised. A window in which commands can flow before the governor
%%%      is up defeats the entire point of putting it here.
%%%
%%%   3. aquacell_twin_sup
%%%      simple_one_for_one over the per-device twins.
%%%      Decision #31: register via {via, gproc, {n, l, {boiler, Mac}}}.
%%%      Decision #32: rehydrate stored energy from Postgres in init/1 and
%%%      checkpoint every few minutes. A deploy must not blank the fleet's
%%%      state. If the last update is older than TWIN_STALE_AFTER_S the state
%%%      is *unknown*, and unknown means fail safe: release the device to its
%%%      mechanical thermostat rather than act on a stale estimate.
%%%
%%%   4. aquacell_mqtt_ingest_sup
%%%      N emqtt workers on a shared subscription (decision #30), device
%%%      hashed to shard so per-device ordering survives. Starts after the
%%%      twins so arriving telemetry has somewhere to go.
%%%
%%%   5. aquacell_schedule_consumer
%%%      Redis Streams consumer group (decision #37); Pub/Sub was rejected
%%%      because it drops schedules silently whenever the consumer is down.
%%%      Decision #38: reject non-increasing schedule_generation so a replayed
%%%      or out-of-order message cannot overwrite a newer plan. Starts last:
%%%      it is the thing that acts on the fleet, so everything that protects
%%%      the fleet is already running by the time it does.
%%%
%%% Note on what does NOT belong in this tree: heavy estimation. Decision #16
%%% puts the particle filter in Python at a 1-5 minute cadence, not inside
%%% Erlang.
%%% @end
%%%-------------------------------------------------------------------
-module(aquacell_sup).

-behaviour(supervisor).

-export([start_link/0]).
-export([init/1]).

-define(SERVER, ?MODULE).

-spec start_link() -> supervisor:startlink_ret().
start_link() ->
    supervisor:start_link({local, ?SERVER}, ?MODULE, []).

-spec init([]) -> {ok, {supervisor:sup_flags(), [supervisor:child_spec()]}}.
init([]) ->
    %% one_for_one: the subsystems above are independent enough that a crash
    %% in one should not restart the others. Revisit if the twins end up
    %% depending on a live ingest connection.
    SupFlags = #{strategy => one_for_one,
                 intensity => 10,
                 period => 60},
    Children = [],
    {ok, {SupFlags, Children}}.
