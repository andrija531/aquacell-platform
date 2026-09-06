#!/usr/bin/env bash
#
# Point a Shelly Gen3 at the AquaCell broker over its local HTTP RPC API.
#
# Usage:
#   scripts/shelly_provision.sh <shelly-ip> <broker-host> <mqtt-password> [broker-port]
#
# TLS is selected with the SHELLY_TLS environment variable:
#   none      plaintext (default). Port defaults to 1883. LAN testing only —
#             the password and all telemetry cross the network in clear.
#   bundle    TLS validated against the device's built-in CA bundle. Port
#             defaults to 8883. Use this with a Let's Encrypt certificate; it
#             needs no per-device setup.
#   user_ca   TLS validated against a CA you uploaded with
#             scripts/shelly_put_ca.sh. Port defaults to 8883.
#   insecure  TLS with validation disabled. Encrypts, but authenticates
#             nothing, so it does not stop an active attacker. Use only to
#             prove a handshake works, never as an end state.
#
# Examples:
#   scripts/shelly_provision.sh 192.168.0.81 192.168.0.37 'SomePassword'
#   SHELLY_TLS=bundle scripts/shelly_provision.sh 192.168.0.81 mqtt.example.com 'SomePassword'
#
# The MQTT username and the topic prefix are both derived from the device's own
# id, which is also its default MQTT client id. That alignment is what lets the
# EMQX ACL scope the device with ${clientid} — see infrastructure/emqx/acl.conf.
#
# What this sets, and why:
#   topic_prefix    aquacell/<device_id>   keeps the fleet in one namespace
#   enable_rpc      true                   the control channel we actually use
#   status_ntf      true                   publish component status on change;
#                                          default is false and without it the
#                                          relay/power telemetry never arrives
#   rpc_ntf         true                   NotifyEvent/NotifyStatus stream
#   enable_control  false                  disables <prefix>/command/... AND
#                                          the fleet-wide shellies/command
#                                          broadcast topic. RPC is enough and
#                                          is per-device; a broadcast command
#                                          channel on a load-control fleet is
#                                          not something to leave switched on.

set -euo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
    echo "usage: $0 <shelly-ip> <broker-host> <mqtt-password> [broker-port]" >&2
    echo "       SHELLY_TLS=none|bundle|user_ca|insecure (default none)" >&2
    exit 64
fi

SHELLY_IP="$1"
BROKER_HOST="$2"
MQTT_PASSWORD="$3"

SHELLY_TLS="${SHELLY_TLS:-none}"
case "${SHELLY_TLS}" in
    none)     SSL_CA_JSON='null'            ; DEFAULT_PORT=1883 ;;
    bundle)   SSL_CA_JSON='"ca.pem"'        ; DEFAULT_PORT=8883 ;;
    user_ca)  SSL_CA_JSON='"user_ca.pem"'   ; DEFAULT_PORT=8883 ;;
    insecure) SSL_CA_JSON='"*"'             ; DEFAULT_PORT=8883 ;;
    *)
        echo "error: SHELLY_TLS must be none, bundle, user_ca or insecure" >&2
        exit 64
        ;;
esac

BROKER_PORT="${4:-${DEFAULT_PORT}}"

if [[ "${SHELLY_TLS}" == "none" ]]; then
    echo "WARNING: plaintext MQTT. The device password and all telemetry will"
    echo "         cross the network unencrypted. Acceptable on a trusted LAN"
    echo "         for a bench test; not acceptable over the internet."
    echo
fi

rpc() {
    local method="$1"
    local params="${2:-}"
    local body
    if [[ -n "${params}" ]]; then
        body="$(printf '{"id":1,"method":"%s","params":%s}' "${method}" "${params}")"
    else
        body="$(printf '{"id":1,"method":"%s"}' "${method}")"
    fi
    curl -fsS --max-time 10 -X POST \
        -H 'Content-Type: application/json' \
        --data-binary "${body}" \
        "http://${SHELLY_IP}/rpc"
}

echo "== 1. identify device =="
info="$(rpc Shelly.GetDeviceInfo)"
echo "${info}"

DEVICE_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"${info}")"
if [[ -z "${DEVICE_ID}" ]]; then
    echo "error: could not read device id" >&2
    exit 1
fi
echo "device id: ${DEVICE_ID}"

TOPIC_PREFIX="aquacell/${DEVICE_ID}"

echo
echo "== 2. current MQTT config =="
rpc MQTT.GetConfig
echo

echo "== 3. apply AquaCell MQTT config (TLS mode: ${SHELLY_TLS}, port ${BROKER_PORT}) =="
config="$(DEVICE_ID="${DEVICE_ID}" \
          SERVER="${BROKER_HOST}:${BROKER_PORT}" \
          PASSWORD="${MQTT_PASSWORD}" \
          PREFIX="${TOPIC_PREFIX}" \
          SSL_CA="${SSL_CA_JSON}" \
          python3 -c '
import json, os
print(json.dumps({"config": {
    "enable":         True,
    "server":         os.environ["SERVER"],
    "user":           os.environ["DEVICE_ID"],
    "pass":           os.environ["PASSWORD"],
    "client_id":      os.environ["DEVICE_ID"],
    "topic_prefix":   os.environ["PREFIX"],
    "enable_rpc":     True,
    "rpc_ntf":        True,
    "status_ntf":     True,
    "enable_control": False,
    "ssl_ca":         json.loads(os.environ["SSL_CA"]),
}}))')"

# The password is in this payload, so the request body is not echoed.
rpc MQTT.SetConfig "${config}"
echo

echo "== 4. reboot to apply =="
rpc Shelly.Reboot
echo
echo "waiting 20s for the device to come back..."
sleep 20

echo
echo "== 5. verify =="
for attempt in 1 2 3 4 5; do
    if status="$(rpc MQTT.GetStatus 2>/dev/null)"; then
        echo "${status}"
        if grep -q '"connected":true' <<<"${status}"; then
            echo
            echo "CONNECTED. device_id=${DEVICE_ID}"
            echo "topic prefix: ${TOPIC_PREFIX}"
            echo
            echo "Control it with:"
            echo "  docker compose exec core_engine bin/aquacell remote_console"
            echo "  shelly_ctl:status(\"${DEVICE_ID}\")."
            echo "  shelly_ctl:on(\"${DEVICE_ID}\")."
            exit 0
        fi
    fi
    echo "not connected yet (attempt ${attempt}/5), retrying in 5s"
    sleep 5
done

echo >&2
echo "device is not reporting an MQTT connection." >&2
echo "Check, in order:" >&2
echo "  1. Does the credential exist?  scripts/emqx_add_user.sh --list" >&2
echo "     The username must equal the device id: ${DEVICE_ID}" >&2
echo "  2. Is the port reachable from the device's network?" >&2
echo "     plaintext: MQTT_TCP_BIND=0.0.0.0 in .env" >&2
echo "     TLS:       MQTT_TLS_BIND=0.0.0.0 in .env" >&2
echo "     then: docker compose up -d --force-recreate emqx" >&2
echo "  3. EMQX logs for an auth or ACL refusal:" >&2
echo "     docker compose logs emqx | tail -50" >&2
if [[ "${SHELLY_TLS}" != "none" ]]; then
    echo "  4. TLS: the device reports only connected:false and never says why," >&2
    echo "     so verify the certificate from another machine:" >&2
    echo "       openssl s_client -connect ${BROKER_HOST}:${BROKER_PORT} -showcerts </dev/null" >&2
    echo "     The name you provisioned (${BROKER_HOST}) must appear in the" >&2
    echo "     certificate's Subject Alternative Name. An IP will not match a" >&2
    echo "     hostname cert, or the reverse." >&2
    if [[ "${SHELLY_TLS}" == "user_ca" ]]; then
        echo "  5. Was the CA actually uploaded?  scripts/shelly_put_ca.sh ${SHELLY_IP}" >&2
    fi
    echo "     To isolate a validation problem from a connectivity one, retry" >&2
    echo "     once with SHELLY_TLS=insecure. If that connects, the transport is" >&2
    echo "     fine and the certificate is the problem. Do not leave it there." >&2
fi
exit 1
