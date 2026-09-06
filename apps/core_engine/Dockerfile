# Build the release with the full OTP image, run it on a slim base.
#
# The release bundles ERTS (relx `{mode, prod}`), so the runtime stage needs no
# Erlang install — only the shared libraries ERTS links against. Both stages
# are Debian bookworm so those libraries match.

FROM erlang:27 AS build

WORKDIR /src

# Dependencies first, so a source-only change does not refetch them.
# rebar.config.script is required here: it sets BUILD_WITHOUT_QUIC, without
# which emqtt drags in the quicer NIF and the build needs a C toolchain.
COPY rebar.config rebar.config.script rebar.lock ./
RUN rebar3 get-deps

COPY config ./config
COPY src ./src
RUN rebar3 release


FROM debian:bookworm-slim AS runtime

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libncurses6 \
      libssl3 \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Run unprivileged. The release needs to write only to its own log and tmp
# directories, both under /opt/aquacell.
RUN useradd --system --create-home --home-dir /opt/aquacell --uid 10001 aquacell

COPY --from=build --chown=aquacell:aquacell /src/_build/default/rel/aquacell /opt/aquacell/rel

USER aquacell
WORKDIR /opt/aquacell/rel

# `foreground` keeps the VM attached to PID 1 so Docker sees crashes and the
# restart policy applies. Attach a shell with:
#   docker compose exec core_engine bin/aquacell remote_console
ENTRYPOINT ["bin/aquacell"]
CMD ["foreground"]
