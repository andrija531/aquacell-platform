%%%-------------------------------------------------------------------
%%% @doc AquaCell application entry point.
%%%
%%% Skeleton. Boots an empty supervision tree so the toolchain and the release
%%% can be verified before any logic exists.
%%% @end
%%%-------------------------------------------------------------------
-module(aquacell_app).

-behaviour(application).

-export([start/2, stop/1]).

-spec start(application:start_type(), term()) -> {ok, pid()} | {error, term()}.
start(_StartType, _StartArgs) ->
    aquacell_sup:start_link().

-spec stop(term()) -> ok.
stop(_State) ->
    ok.
