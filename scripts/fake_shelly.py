#!/usr/bin/env python3
"""
Minimal fake Shelly Gen3, speaking the RPC-over-MQTT channel.

Exists so the Erlang control path can be exercised without the physical relay,
and so a failure can be localised: if shelly_ctl works against this and not
against the real device, the problem is the device's configuration or the
network, not the broker or the Erlang side.

It implements only what the POC calls: Shelly.GetDeviceInfo, Switch.GetStatus,
Switch.Set, Switch.Toggle. It holds a relay state in memory and reports a
plausible power draw when closed.

Usage (on the compose network, so it can resolve "emqx"):

    docker run --rm --network aquacell_default \\
      -v "$PWD/scripts/fake_shelly.py":/app/fake_shelly.py \\
      -e MQTT_HOST=emqx -e SHELLY_ID=shelly1pmg3-aabbccddeeff \\
      -e MQTT_PASSWORD=... \\
      python:3.12-slim bash -c "pip -q install paho-mqtt && python /app/fake_shelly.py"
"""

import json
import os
import sys
import time

import paho.mqtt.client as mqtt

HOST = os.environ.get("MQTT_HOST", "127.0.0.1")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
DEVICE_ID = os.environ.get("SHELLY_ID", "shelly1pmg3-aabbccddeeff")
PASSWORD = os.environ.get("MQTT_PASSWORD", "")

PREFIX = f"aquacell/{DEVICE_ID}"
NOMINAL_W = float(os.environ.get("NOMINAL_W", "2000"))

state = {"output": False}


def switch_status():
    return {
        "id": 0,
        "source": "MQTT",
        "output": state["output"],
        "apower": NOMINAL_W if state["output"] else 0.0,
        "voltage": 231.4,
        "current": (NOMINAL_W / 231.4) if state["output"] else 0.0,
        "aenergy": {"total": 1234.5, "by_minute": [0, 0, 0], "minute_ts": int(time.time())},
        "temperature": {"tC": 41.2, "tF": 106.2},
    }


def publish_status(client):
    client.publish(f"{PREFIX}/status/switch:0", json.dumps(switch_status()), qos=1)


def on_connect(client, userdata, flags, rc, properties=None):
    if rc != 0:
        print(f"connect refused, rc={rc}", flush=True)
        return
    print(f"connected as {DEVICE_ID}", flush=True)
    client.subscribe(f"{PREFIX}/rpc", qos=1)
    # The real device publishes this as a retained LWT-paired message.
    client.publish(f"{PREFIX}/online", "true", qos=1, retain=True)
    publish_status(client)


def on_message(client, userdata, msg):
    try:
        req = json.loads(msg.payload)
    except ValueError:
        print(f"undecodable request: {msg.payload!r}", flush=True)
        return

    method = req.get("method")
    params = req.get("params") or {}
    src = req.get("src")
    print(f"rpc <- {method} {params}", flush=True)

    if method == "Shelly.GetDeviceInfo":
        result = {
            "id": DEVICE_ID,
            "mac": DEVICE_ID.split("-")[-1].upper(),
            "model": "S3SW-001P16EU",
            "gen": 3,
            "fw_id": "20241011-114455/1.4.4-g6d2a586",
            "ver": "1.4.4",
            "app": "S1PMG3",
            "auth_en": False,
        }
    elif method == "Switch.GetStatus":
        result = switch_status()
    elif method == "Switch.Set":
        was_on = state["output"]
        state["output"] = bool(params.get("on", False))
        result = {"was_on": was_on}
        publish_status(client)
    elif method == "Switch.Toggle":
        was_on = state["output"]
        state["output"] = not was_on
        result = {"was_on": was_on}
        publish_status(client)
    else:
        err = {"id": req.get("id"), "src": DEVICE_ID, "dst": src,
               "error": {"code": -105, "message": f"unknown method {method}"}}
        client.publish(f"{src}/rpc", json.dumps(err), qos=1)
        return

    response = {"id": req.get("id"), "src": DEVICE_ID, "dst": src, "result": result}
    client.publish(f"{src}/rpc", json.dumps(response), qos=1)
    print(f"rpc -> {result}", flush=True)


def main():
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=DEVICE_ID,
        protocol=mqtt.MQTTv5,
    )
    client.username_pw_set(DEVICE_ID, PASSWORD)
    # Matches the real device: a last will on the online topic.
    client.will_set(f"{PREFIX}/online", "false", qos=1, retain=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(HOST, PORT, keepalive=60)
    print(f"fake shelly {DEVICE_ID} -> {HOST}:{PORT}", flush=True)
    client.loop_forever()


if __name__ == "__main__":
    sys.exit(main())
