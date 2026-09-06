%%%-------------------------------------------------------------------
%%% @doc Shelly MQTT connection and RPC channel.
%%%
%%% ONE emqtt connection, subscribing to plain wildcards. That is deliberate
%%% for a proof of concept with a single device, and it is NOT the production
%%% ingest path: decision #30 requires EMQX shared subscriptions with N worker
%%% processes hashed by device, because a single wildcard subscriber funnels
%%% every message through one mailbox and will queue and OOM on a reconnect
%%% storm. At one device that cannot happen. At a thousand it will.
%%%
%%% Likewise there is no ramp governor in front of this yet (decision #54).
%%% Manual control of one relay on a bench is fine. Nothing here is safe to
%%% point at a fleet.
%%%
%%% Protocol, from the Shelly Gen2+ RPC-over-MQTT channel:
%%%
%%%   request   -> aquacell/<did>/rpc
%%%                {"id": N, "src": "aquacell/ctl/<did>", "method": M,
%%%                 "params": {...}}
%%%   response  <- aquacell/ctl/<did>/rpc
%%%                {"id": N, "src": "<did>", "dst": "aquacell/ctl/<did>",
%%%                 "result": {...}}   or   {..., "error": {...}}
%%%
%%% The device appends "/rpc" to whatever `src` the caller supplied. Requests
%%% are correlated by `id`, which is why this process keeps a pending map and
%%% replies to the original caller rather than exposing a cast-and-hope API.
%%% @end
%%%-------------------------------------------------------------------
-module(aquacell_shelly).

-behaviour(gen_server).

%% API
-export([start_link/0]).
-export([rpc/2, rpc/3, rpc/4]).
-export([devices/0, connected/0]).

%% gen_server callbacks
-export([init/1, handle_call/3, handle_cast/2, handle_info/2, terminate/2]).

-define(SERVER, ?MODULE).
-define(DEFAULT_RPC_TIMEOUT, 5000).

-type device_id() :: binary() | string().

-record(state, {
    conn :: pid() | undefined,
    next_id = 1 :: pos_integer(),
    %% request id => {From, TimerRef}
    pending = #{} :: #{pos_integer() => {gen_server:from(), reference()}},
    %% device id => #{online, switch, last_seen}
    devices = #{} :: #{binary() => map()}
}).

%%====================================================================
%% API
%%====================================================================

-spec start_link() -> gen_server:start_ret().
start_link() ->
    gen_server:start_link({local, ?SERVER}, ?MODULE, [], []).

%% @doc Call a Shelly RPC method with no parameters.
-spec rpc(device_id(), binary()) -> {ok, term()} | {error, term()}.
rpc(DeviceId, Method) ->
    rpc(DeviceId, Method, #{}, ?DEFAULT_RPC_TIMEOUT).

-spec rpc(device_id(), binary(), map()) -> {ok, term()} | {error, term()}.
rpc(DeviceId, Method, Params) ->
    rpc(DeviceId, Method, Params, ?DEFAULT_RPC_TIMEOUT).

%% @doc Call a Shelly RPC method and wait for the device's response.
-spec rpc(device_id(), binary(), map(), timeout()) -> {ok, term()} | {error, term()}.
rpc(DeviceId, Method, Params, Timeout) ->
    Did = to_bin(DeviceId),
    %% The gen_server timeout is deliberately longer than the RPC timeout: the
    %% server itself answers late requests with {error, timeout}, and we want
    %% that answer rather than an exit from the caller.
    gen_server:call(?SERVER, {rpc, Did, Method, Params, Timeout}, Timeout + 1000).

%% @doc Everything the server has heard from, and what it last said.
-spec devices() -> #{binary() => map()}.
devices() ->
    gen_server:call(?SERVER, devices).

%% @doc Whether the MQTT connection to the broker is up.
-spec connected() -> boolean().
connected() ->
    gen_server:call(?SERVER, connected).

%%====================================================================
%% gen_server
%%====================================================================

-spec init([]) -> {ok, #state{}}.
init([]) ->
    process_flag(trap_exit, true),
    self() ! connect,
    {ok, #state{}}.

-spec handle_call(term(), gen_server:from(), #state{}) ->
          {reply, term(), #state{}} | {noreply, #state{}}.
handle_call({rpc, _Did, _M, _P, _T}, _From, #state{conn = undefined} = S) ->
    {reply, {error, not_connected}, S};
handle_call({rpc, Did, Method, Params, Timeout}, From,
            #state{conn = Conn, next_id = Id, pending = Pending} = S) ->
    Frame0 = #{<<"id">> => Id,
               <<"src">> => reply_base(Did),
               <<"method">> => Method},
    Frame = case map_size(Params) of
                0 -> Frame0;
                _ -> Frame0#{<<"params">> => Params}
            end,
    Payload = iolist_to_binary(json:encode(Frame)),
    Topic = <<"aquacell/", Did/binary, "/rpc">>,
    case emqtt:publish(Conn, Topic, Payload, 1) of
        ok ->
            TRef = erlang:start_timer(Timeout, self(), {rpc_timeout, Id}),
            {noreply, S#state{next_id = Id + 1,
                              pending = Pending#{Id => {From, TRef}}}};
        {ok, _PacketId} ->
            TRef = erlang:start_timer(Timeout, self(), {rpc_timeout, Id}),
            {noreply, S#state{next_id = Id + 1,
                              pending = Pending#{Id => {From, TRef}}}};
        {error, Reason} ->
            {reply, {error, {publish_failed, Reason}}, S}
    end;
handle_call(devices, _From, #state{devices = D} = S) ->
    {reply, D, S};
handle_call(connected, _From, #state{conn = C} = S) ->
    {reply, C =/= undefined, S};
handle_call(Other, _From, S) ->
    {reply, {error, {unknown_call, Other}}, S}.

-spec handle_cast(term(), #state{}) -> {noreply, #state{}}.
handle_cast(_Msg, S) ->
    {noreply, S}.

-spec handle_info(term(), #state{}) -> {noreply, #state{}}.
handle_info(connect, S) ->
    case do_connect() of
        {ok, Conn} ->
            logger:info("shelly: connected to broker, subscriptions active"),
            {noreply, S#state{conn = Conn}};
        {error, Reason} ->
            %% Deliberately simple: fixed retry. The device's own fail-safe
            %% (edge_scripts/connection_fallback.js) is what protects comfort
            %% when the server side is down, not this loop.
            logger:warning("shelly: connect failed (~p), retrying in 5s", [Reason]),
            erlang:send_after(5000, self(), connect),
            {noreply, S}
    end;

%% RPC response from a device.
handle_info({publish, #{topic := Topic, payload := Payload}}, S) ->
    {noreply, handle_publish(Topic, Payload, S)};

handle_info({timeout, _Timer, {rpc_timeout, Id}}, #state{pending = Pending} = S) ->
    case maps:take(Id, Pending) of
        {{From, _TRef}, Rest} ->
            gen_server:reply(From, {error, timeout}),
            {noreply, S#state{pending = Rest}};
        error ->
            {noreply, S}
    end;

handle_info({'EXIT', Conn, Reason}, #state{conn = Conn} = S) ->
    logger:warning("shelly: mqtt connection down (~p), reconnecting", [Reason]),
    erlang:send_after(1000, self(), connect),
    {noreply, S#state{conn = undefined}};

handle_info({disconnected, ReasonCode, _Props}, S) ->
    logger:warning("shelly: broker disconnected us, reason ~p", [ReasonCode]),
    {noreply, S};

handle_info(_Info, S) ->
    {noreply, S}.

-spec terminate(term(), #state{}) -> ok.
terminate(_Reason, #state{conn = undefined}) ->
    ok;
terminate(_Reason, #state{conn = Conn}) ->
    catch emqtt:disconnect(Conn),
    ok.

%%====================================================================
%% Internal
%%====================================================================

-spec do_connect() -> {ok, pid()} | {error, term()}.
do_connect() ->
    Host = env_str("MQTT_HOST", "emqx"),
    Port = env_int("MQTT_PORT", 1883),
    User = env_str("MQTT_CORE_USERNAME", "core_engine"),
    Pass = env_str("MQTT_CORE_PASSWORD", ""),
    ClientId = env_str("MQTT_CLIENT_ID", "core_engine"),
    Opts = [{host, Host},
            {port, Port},
            {clientid, list_to_binary(ClientId)},
            {username, list_to_binary(User)},
            {password, list_to_binary(Pass)},
            {owner, self()},
            {clean_start, true},
            {proto_ver, v5},
            {keepalive, 60}],
    case emqtt:start_link(Opts) of
        {ok, Conn} ->
            case emqtt:connect(Conn) of
                {ok, _Props} ->
                    ok = subscribe_all(Conn),
                    {ok, Conn};
                {error, Reason} ->
                    catch emqtt:stop(Conn),
                    {error, Reason}
            end;
        {error, Reason} ->
            {error, Reason}
    end.

-spec subscribe_all(pid()) -> ok.
subscribe_all(Conn) ->
    Filters = [<<"aquacell/ctl/+/rpc">>,
               <<"aquacell/+/status/#">>,
               <<"aquacell/+/events/rpc">>,
               <<"aquacell/+/online">>],
    lists:foreach(
      fun(F) ->
              case emqtt:subscribe(Conn, {F, 1}) of
                  {ok, _, _} -> ok;
                  ok -> ok;
                  Other ->
                      %% An ACL refusal shows up here as a failure code rather
                      %% than a crash, and it is the most likely thing to go
                      %% wrong on a fresh broker, so say so loudly.
                      logger:error("shelly: subscribe ~s refused: ~p", [F, Other])
              end
      end, Filters).

-spec handle_publish(binary(), binary(), #state{}) -> #state{}.
handle_publish(Topic, Payload, S) ->
    case binary:split(Topic, <<"/">>, [global]) of
        %% aquacell/ctl/<did>/rpc  -> RPC response
        [<<"aquacell">>, <<"ctl">>, Did, <<"rpc">>] ->
            handle_rpc_response(Did, Payload, S);
        %% aquacell/<did>/online
        [<<"aquacell">>, Did, <<"online">>] ->
            Online = Payload =:= <<"true">>,
            logger:info("shelly: ~s online=~p", [Did, Online]),
            update_device(Did, #{online => Online}, S);
        %% aquacell/<did>/status/<component>
        [<<"aquacell">>, Did, <<"status">>, Component] ->
            case safe_decode(Payload) of
                {ok, Status} ->
                    update_device(Did, #{Component => Status}, S);
                {error, _} ->
                    S
            end;
        %% aquacell/<did>/events/rpc
        [<<"aquacell">>, Did, <<"events">>, <<"rpc">>] ->
            logger:debug("shelly: ~s event ~s", [Did, Payload]),
            S;
        _ ->
            S
    end.

-spec handle_rpc_response(binary(), binary(), #state{}) -> #state{}.
handle_rpc_response(Did, Payload, #state{pending = Pending} = S) ->
    case safe_decode(Payload) of
        {ok, #{<<"id">> := Id} = Frame} ->
            Reply = case Frame of
                        #{<<"result">> := Result} -> {ok, Result};
                        #{<<"error">> := Error} -> {error, Error};
                        _ -> {error, {malformed_response, Frame}}
                    end,
            case maps:take(Id, Pending) of
                {{From, TRef}, Rest} ->
                    _ = erlang:cancel_timer(TRef),
                    gen_server:reply(From, Reply),
                    S#state{pending = Rest};
                error ->
                    %% Late response after we already timed out, or a reply to
                    %% a request from another node. Not an error.
                    logger:debug("shelly: unmatched rpc response id=~p from ~s",
                                 [Id, Did]),
                    S
            end;
        {ok, Other} ->
            logger:warning("shelly: rpc response without id from ~s: ~p", [Did, Other]),
            S;
        {error, Reason} ->
            logger:warning("shelly: undecodable rpc response from ~s: ~p", [Did, Reason]),
            S
    end.

-spec update_device(binary(), map(), #state{}) -> #state{}.
update_device(Did, Fields, #state{devices = Devices} = S) ->
    Existing = maps:get(Did, Devices, #{}),
    Updated = maps:merge(Existing, Fields#{last_seen => erlang:system_time(second)}),
    S#state{devices = Devices#{Did => Updated}}.

-spec reply_base(binary()) -> binary().
reply_base(Did) ->
    <<"aquacell/ctl/", Did/binary>>.

-spec safe_decode(binary()) -> {ok, term()} | {error, term()}.
safe_decode(Payload) ->
    try
        {ok, json:decode(Payload)}
    catch
        Class:Reason -> {error, {Class, Reason}}
    end.

-spec to_bin(device_id()) -> binary().
to_bin(B) when is_binary(B) -> B;
to_bin(L) when is_list(L) -> list_to_binary(L).

-spec env_str(string(), string()) -> string().
env_str(Name, Default) ->
    case os:getenv(Name) of
        false -> Default;
        "" -> Default;
        V -> V
    end.

-spec env_int(string(), integer()) -> integer().
env_int(Name, Default) ->
    case os:getenv(Name) of
        false -> Default;
        "" -> Default;
        V -> list_to_integer(V)
    end.
