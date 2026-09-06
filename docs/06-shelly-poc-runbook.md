# Shelly 1PM Gen3 POC runbook

Goal: one real Shelly connected to EMQX, controlled by hand from the Erlang
container. This proves the transport and the control path. It proves nothing
about the virtual sensor, the estimator or the market.

## Before you wire anything

**Do not put the relay in series with a 2 kW heating element yet.**

The Shelly 1PM Gen3 is rated 16 A resistive but only **2000 W maximum
switching power at 240 VAC**. A 2 kW element at 230 V sits *at* that limit and
3 kW elements exceed it. Relay endurance for this class of part is quoted in
the 10⁴–10⁵ cycle range at rated resistive load, and a 15-minute probe cadence
is ~35 k cycles/year — the contacts are consumed in about two years, and a
fleet-wide relay failure means truck rolls, which is the one cost that
destroys the CapEx case.

Decisions #39 and #41: the Shelly drives a **DIN modular contactor** (~€10–15,
designed for 10⁵–10⁶ operations) and the contactor switches the element. For
this POC, test against no load or something trivial like a lamp. Wiring it to
the boiler is a separate step that needs the contactor in hand.

## What you need

- Server LAN IP. Yours is **192.168.0.37**.
- The Shelly's IP once it joins your wifi. Find it in the Shelly app, on your
  router's DHCP lease table, or with `nmap -sn 192.168.0.0/24`.
- `.env` present and filled in (`cp .env.example .env`).

## 1. Publish the broker on the LAN

Every port is bound to `127.0.0.1` by default, so the Shelly cannot reach it.

In `.env`:

```
MQTT_BIND_ADDR=0.0.0.0
MQTT_CORE_PASSWORD=<pick something>
```

Then:

```bash
docker compose up -d emqx
docker compose ps          # wait for healthy
```

This exposes **plaintext MQTT on your LAN**. The device password crosses the
network in clear and so does the telemetry. Acceptable on a home network for a
bench test; not acceptable beyond that. Decision #53 wants TLS on 8883 with
per-device certificates, and `infrastructure/emqx/emqx.conf` has the settings
to switch to, commented, next to the current ones.

## 2. Create the MQTT credentials

Per-device credentials, never a shared password (decision #53) — a homeowner
can read their own Shelly's config over its local HTTP API.

```bash
# For the Erlang core
./scripts/emqx_add_user.sh core_engine "$(grep '^MQTT_CORE_PASSWORD=' .env | cut -d= -f2-)"

# For the device. The username MUST equal the Shelly's device id, because the
# ACL scopes each client with ${clientid} and the Shelly's default MQTT client
# id is its device id. Get the id from step 3 first if you don't know it.
./scripts/emqx_add_user.sh shelly1pmg3-XXXXXXXXXXXX 'DevicePassword'

./scripts/emqx_add_user.sh --list
```

## 3. Point the Shelly at the broker

```bash
./scripts/shelly_provision.sh <shelly-ip> 192.168.0.37 'DevicePassword'
```

The script reads the device id, applies the MQTT config, reboots, and waits for
the device to report `connected: true`. It prints the device id — you need it
for step 5.

What it sets and why:

| Setting | Value | Reason |
|---|---|---|
| `topic_prefix` | `aquacell/<device_id>` | keeps the fleet in one namespace so the ACL can scope it |
| `enable_rpc` | true | the control channel |
| `status_ntf` | **true** | defaults to false; without it you get no relay/power telemetry at all |
| `rpc_ntf` | true | NotifyStatus / NotifyEvent stream |
| `enable_control` | **false** | disables `<prefix>/command/...` *and* the fleet-wide `shellies/command` broadcast topic. A broadcast command channel on a load-control fleet is not something to leave on. |

If it fails, the script tells you what to check. The most likely cause is a
missing credential or `MQTT_BIND_ADDR` still on loopback.

## 4. Start the Erlang core

```bash
docker compose up -d --build core_engine
docker compose logs -f core_engine
```

Look for:

```
shelly: connected to broker, subscriptions active
shelly: shelly1pmg3-XXXXXXXXXXXX online=true
```

If you see `subscribe ... refused`, the ACL rejected a filter — check
`docker compose logs emqx`.

## 5. Control it

```bash
docker compose exec core_engine bin/aquacell remote_console
```

Then, with your device id:

```erlang
Did = "shelly1pmg3-XXXXXXXXXXXX".

shelly_ctl:ls().          % devices heard from, with cached status
shelly_ctl:info(Did).     % model, firmware, mac
shelly_ctl:status(Did).   % output state, apower, voltage, energy counter
shelly_ctl:on(Did).       % close the relay
shelly_ctl:off(Did).      % open it
shelly_ctl:toggle(Did).
shelly_ctl:power(Did).    % just the watts
```

Detach with `Ctrl-G q` — **not** `q().`, which stops the node.

`bin/aquacell eval "shelly_ctl:power(\"...\")."` works for one-shot calls from
a script, but renders binaries as byte lists. `remote_console` is nicer to read.

## Deploying to a remote server (Hetzner)

The LAN walkthrough above uses plaintext MQTT, which is fine on your own
network and **not** fine across the internet. On a public host, port 1883
carries the device password and all telemetry in clear, and anyone scanning the
address can reach the broker. Use TLS on 8883 and leave 1883 unpublished.

Note what `verify_none` in `emqx.conf` does and does not mean. It controls
whether EMQX demands a certificate *from the client*. With a real certificate
on the listener, traffic on 8883 is encrypted and **the device validates the
broker** — that is the direction that stops an impostor broker and a passive
eavesdropper. What is still missing is mTLS, where the broker also
cryptographically identifies the device instead of trusting a password.
Decision #53 wants that, the Shelly supports it
(`Shelly.PutTLSClientCert` / `PutTLSClientKey`, then `use_client_cert=true`),
and it is the natural next step once one device works.

### Which certificate

**With a DNS name pointing at the server — strongly preferred.** The Shelly
carries a built-in CA bundle covering the usual public authorities, so a Let's
Encrypt certificate validates with no per-device setup. That matters at fleet
scale: a private CA has to be uploaded to every device you ever install, and
re-uploaded whenever it expires.

```bash
# On the server, with mqtt.example.com pointing at it and 80/tcp briefly open
sudo apt install certbot
sudo certbot certonly --standalone -d mqtt.example.com

sudo cp /etc/letsencrypt/live/mqtt.example.com/{fullchain.pem,privkey.pem} \
        infrastructure/emqx/certs/
sudo chmod 644 infrastructure/emqx/certs/{fullchain.pem,privkey.pem}
```

In `.env`:

```
MQTT_TLS_BIND=0.0.0.0
MQTT_TCP_BIND=127.0.0.1
MQTT_TLS_CERTFILE=/opt/emqx/etc/certs/aquacell/fullchain.pem
MQTT_TLS_KEYFILE=/opt/emqx/etc/certs/aquacell/privkey.pem
```

Renewal replaces the files on the host; EMQX needs a restart to pick them up,
so add a certbot deploy hook that runs
`docker compose up -d --force-recreate emqx`. Without it the certificate
silently expires in 90 days and the whole fleet drops off.

**IP address only.** Generate a private CA and upload it to the device:

```bash
./scripts/make_server_cert.sh <server-public-ip>
# .env: MQTT_TLS_CERTFILE=/opt/emqx/etc/certs/aquacell/server.crt
#       MQTT_TLS_KEYFILE=/opt/emqx/etc/certs/aquacell/server.key
./scripts/shelly_put_ca.sh 192.168.0.81
```

The address in the certificate must be **exactly** what the device connects
to. A certificate issued for an IP will not validate against a hostname or the
reverse, and the Shelly reports only `connected: false` with no reason — so
this mismatch is the single most likely thing to waste your afternoon.

### Firewall

Open **8883 only**. Postgres, Redis and the dashboard must never be exposed;
the compose file pins the dashboard to loopback, and you reach it over SSH:

```bash
ssh -L 18083:127.0.0.1:18083 user@server   # then http://127.0.0.1:18083
```

If you use the Hetzner Cloud Firewall, allow 22 and 8883 inbound and nothing
else. With `ufw` on the host, remember Docker publishes ports by writing
straight into iptables and can bypass ufw rules — binding to `127.0.0.1`, as
this compose file does for everything except 8883, is what actually keeps those
services private.

### Your device, concretely

Device id `shelly1pmg3-28372f3978f4`, firmware 1.4.0. Verified: the ACL
accepts exactly this id over TLS with a validating client.

```bash
# On the server
./scripts/emqx_add_user.sh core_engine "$(grep '^MQTT_CORE_PASSWORD=' .env | cut -d= -f2-)"
./scripts/emqx_add_user.sh shelly1pmg3-28372f3978f4 'DevicePassword'
docker compose up -d --build

# From your laptop, on the same LAN as the Shelly
SHELLY_TLS=bundle ./scripts/shelly_provision.sh \
    192.168.0.81 mqtt.example.com 'DevicePassword'
```

Or fill the form you already have open at
`http://192.168.0.81/#/settings/mqtt` by hand:

| Field | Value |
|---|---|
| Enable | ✅ |
| Connection type | TLS validated by the **built-in CA bundle** (`ca.pem`). Use *user CA* (`user_ca.pem`) if you generated a private CA. Never leave it on *No TLS* for a remote server. |
| MQTT prefix | `aquacell/shelly1pmg3-28372f3978f4` |
| Use client certificate | ☐ (until mTLS is set up) |
| Enable 'MQTT Control' | ☐ **leave unchecked** |
| Enable RPC over MQTT | ✅ |
| RPC status notifications over MQTT | ✅ |
| Generic status update over MQTT | ✅ **must be on** |
| Server | `mqtt.example.com:8883` |
| Client ID | `shelly1pmg3-28372f3978f4` |
| Username | `shelly1pmg3-28372f3978f4` |
| Password | the one you gave `emqx_add_user.sh` |

Then Save and reboot.

Three of those are load-bearing and easy to get wrong:

- **MQTT prefix must be `aquacell/<device_id>`**, not the default bare device
  id. The ACL scopes each client with `${clientid}` under the `aquacell/`
  namespace; with the default prefix every publish is denied and, because
  `deny_action = disconnect`, the device is dropped rather than told why.
- **Generic status update** is `status_ntf`, and it defaults to *off*. Without
  it you get no relay state and no power readings — which is the entire input
  to the virtual sensor.
- **MQTT Control** must stay off. It is a second, weaker control path, and it
  makes the device subscribe to the fleet-wide `shellies/command` broadcast
  topic. The ACL denies `shellies/#` anyway, and with `deny_action = disconnect`
  a device that tries it gets kicked — so leaving the box ticked can look like
  a mysterious connection failure.

### Username must equal the device id

`emqx_add_user.sh shelly1pmg3-28372f3978f4` is not a naming convention, it is
load-bearing: the ACL uses `${clientid}`, and the Shelly's client id defaults to
its device id. A mismatch means every publish is denied.

## Testing without the device

`scripts/fake_shelly.py` is a minimal Shelly simulator speaking the same RPC
channel. It is how this POC was verified before any hardware existed, and it is
the fastest way to tell whether a problem is in the device or in the platform.

```bash
docker compose up -d emqx
./scripts/emqx_add_user.sh core_engine CorePass123
./scripts/emqx_add_user.sh shelly1pmg3-aabbccddeeff DevPass123

docker run -d --name fake-shelly --network aquacell_default \
  -v "$PWD/scripts/fake_shelly.py":/app/fake_shelly.py:ro \
  -e MQTT_HOST=emqx -e SHELLY_ID=shelly1pmg3-aabbccddeeff -e MQTT_PASSWORD=DevPass123 \
  python:3.12-slim bash -c "pip -q install paho-mqtt && python /app/fake_shelly.py"

docker compose up -d --build core_engine
docker compose exec core_engine bin/aquacell eval \
  "shelly_ctl:on(\"shelly1pmg3-aabbccddeeff\")."
```

Clean up with `docker rm -f fake-shelly`.

## Topic scheme

Set by the firmware; only `topic_prefix` is ours to choose.

```
device -> server   aquacell/<did>/online              "true" / "false" (LWT)
                   aquacell/<did>/events/rpc          NotifyStatus / NotifyEvent
                   aquacell/<did>/status/switch:0     full component status
                   aquacell/ctl/<did>/rpc             RPC responses

server -> device   aquacell/<did>/rpc                 RPC requests
```

A Shelly replies to `<src>/rpc`, where `src` is whatever the caller put in the
request. Setting `src` to `aquacell/ctl/<did>` keeps the device id in the reply
topic so the ACL can scope it with `${clientid}`. A single shared reply topic
would let any device forge responses on behalf of any other — verified: a
device attempting exactly that is disconnected.

## What this POC is not

- **No ramp governor.** Decision #54 puts a hard aggregate kW/min limit in
  Erlang on the last hop. It does not exist yet. `shelly_ctl:on/1` switches
  immediately. Fine for one relay on a bench; not a fleet control path.
- **No comfort constraint.** No reserve floor, no interval observer, no
  estimator. Nothing stops you leaving the element off through a shower.
- **Single wildcard subscriber.** `aquacell_shelly` is one MQTT connection on
  plain wildcards, which decision #30 explicitly rejects for the fleet: one
  mailbox for every message queues and OOMs on a reconnect storm. It must be
  replaced by shared subscriptions with N workers hashed by device.
- **No persistence.** State is in the gen_server and dies with it. Decision
  #32 wants rehydration from Postgres with a stale-state policy that fails safe
  to the mechanical thermostat.
- **`edge_scripts/connection_fallback.js` is not installed** by any of this. It
  still has never run on hardware. Installing it is a good next step, since
  fail-safe ON is what keeps the customer in hot water when the server dies.

## First measurements worth taking

Once it switches reliably, the Phase 0 questions from `docs/05-sinteza.md` §8:

1. Let the tank sit idle overnight and time a reheat to cut-out. If it is
   ~22 minutes the `E_hyst` model holds; if it is ~8 the thermostat probe sits
   differently than modelled, and §6.4 says that parameter is the only tuned
   one in the physics.
2. Watch for the cut-out anchor: commanded ON, power drops 2000 W → 0 W.
   Confirm it actually appears in `aquacell/<did>/status/switch:0`.
3. Measure real standing loss from duty cycle over a quiet night — but note
   decision correction #3: a genuine 15-hour idle window basically never
   happens unless nobody is home.
