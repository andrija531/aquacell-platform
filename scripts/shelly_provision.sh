#!/usr/bin/env bash
#
# Point a Shelly Gen3 at the AquaCell broker over its local HTTP RPC API.
#
# Usage:
#   scripts/shelly_provision.sh <shelly-ip> <broker-host> <mqtt-password> [broker-port]
#
# Example:
#   scripts/shelly_provision.sh 192.168.0.51 192.168.0.37 'SomePassword'
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
    exit 64
fi

SHELLY_IP="$1"
BROKER_HOST="$2"
MQTT_PASSWORD="$3"
BROKER_PORT="${4:-1883}"

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

echo "== 3. apply AquaCell MQTT config =="
config="$(DEVICE_ID="${DEVICE_ID}" \
          SERVER="${BROKER_HOST}:${BROKER_PORT}" \
          PASSWORD="${MQTT_PASSWORD}" \
          PREFIX="${TOPIC_PREFIX}" \
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
    "ssl_ca":         None,
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
echo "  2. Is 1883 reachable from the LAN? MQTT_BIND_ADDR=0.0.0.0 in .env," >&2
echo "     then: docker compose up -d emqx" >&2
echo "  3. EMQX logs for an auth or ACL refusal:" >&2
echo "     docker compose logs emqx | tail -50" >&2
exit 1
