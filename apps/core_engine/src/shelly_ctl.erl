%%%-------------------------------------------------------------------
%%% @doc Manual control of a Shelly, for use from the Erlang console.
%%%
%%% This is the POC's user interface. Attach with:
%%%
%%%     docker compose exec core_engine bin/aquacell remote_console
%%%
%%% then, with Did = "shelly1pmg3-xxxxxxxxxxxx":
%%%
%%%     shelly_ctl:ls().                 %% what has reported in
%%%     shelly_ctl:info(Did).            %% firmware, model, mac
%%%     shelly_ctl:status(Did).          %% relay state and power right now
%%%     shelly_ctl:on(Did).
%%%     shelly_ctl:off(Did).
%%%     shelly_ctl:toggle(Did).
%%%     shelly_ctl:power(Did).           %% just the watts
%%%
%%% There is no ramp governor and no comfort constraint behind these calls
%%% (decisions #54 and #20). They switch the relay immediately. That is
%%% acceptable for one device on a bench and is not a control path for a
%%% fleet.
%%% @end
%%%-------------------------------------------------------------------
-module(shelly_ctl).

-export([ls/0, info/1, status/1, on/1, off/1, toggle/1, set/2, power/1]).

-type device_id() :: binary() | string().

%% @doc Devices the core engine has heard from since it started.
-spec ls() -> #{binary() => map()}.
ls() ->
    aquacell_shelly:devices().

%% @doc Model, firmware version, MAC.
-spec info(device_id()) -> {ok, map()} | {error, term()}.
info(Did) ->
    aquacell_shelly:rpc(Did, <<"Shelly.GetDeviceInfo">>).

%% @doc Full switch status: output state, power, voltage, energy counter.
-spec status(device_id()) -> {ok, map()} | {error, term()}.
status(Did) ->
    aquacell_shelly:rpc(Did, <<"Switch.GetStatus">>, #{<<"id">> => 0}).

%% @doc Close the relay.
-spec on(device_id()) -> {ok, map()} | {error, term()}.
on(Did) ->
    set(Did, true).

%% @doc Open the relay.
-spec off(device_id()) -> {ok, map()} | {error, term()}.
off(Did) ->
    set(Did, false).

-spec set(device_id(), boolean()) -> {ok, map()} | {error, term()}.
set(Did, On) when is_boolean(On) ->
    aquacell_shelly:rpc(Did, <<"Switch.Set">>, #{<<"id">> => 0, <<"on">> => On}).

-spec toggle(device_id()) -> {ok, map()} | {error, term()}.
toggle(Did) ->
    aquacell_shelly:rpc(Did, <<"Switch.Toggle">>, #{<<"id">> => 0}).

%% @doc Active power in watts. This is one of the two signals the whole
%% virtual sensor is built on, the other being relay state, so it is worth
%% having a one-word way to read it.
-spec power(device_id()) -> {ok, number()} | {error, term()}.
power(Did) ->
    case status(Did) of
        {ok, #{<<"apower">> := W}} -> {ok, W};
        {ok, Other} -> {error, {no_apower_field, Other}};
        {error, Reason} -> {error, Reason}
    end.
