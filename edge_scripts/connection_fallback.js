// AquaCell edge safety net — Shelly 1PM Gen3, mJS.
//
// Purpose: if the link to the server dies, hand the water heater back to its
// mechanical thermostat by closing the relay and leaving it closed. The
// customer never notices. Decision #43: fail to ON, not OFF.
//
// The subtlety is decision #44. Naive fail-ON is a CORRELATED fleet event: an
// EMQX restart, a Hetzner blip or one Croatian ISP outage drops thousands of
// devices in the same second, and every one of them closes its relay at the
// same instant. That is precisely the thundering herd the fleet
// desynchronisation work exists to prevent, triggered by the safety net
// itself. So the recovery is spread over a window, per device, computed here
// on the device with no server involvement (decision #45).
//
// This is one of three independent nets (decision #47). The other two are
// Shelly configuration, not script, and must be set at commissioning:
//   1. Relay power-on default state = ON.
//   2. A built-in Shelly schedule that closes the relay daily.
//   3. This script, with "Run on startup" enabled.
// mJS has very little RAM and scripts do crash. If this one dies, 1 and 2
// still deliver hot water.
//
// LIMITATION: untested against hardware. Written from the documented mJS API.
// Verify on the Prečko unit before any fleet rollout.

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

let RELAY_ID = 0;

// How often to check the link.
let TICK_MS = 60 * 1000;

// Consecutive failed ticks before the link is declared dead. Must be long
// enough to ride out a planned broker restart without the whole fleet
// reacting: the architecture review asks for 10-15 minutes.
let GRACE_TICKS = 12;

// Width of the desynchronisation window, seconds. Decision #45.
let SPREAD_S = 300;

// While the link stays down, re-close the relay periodically in case
// something else opened it. Cheap insurance, no server involvement.
let REASSERT_EVERY_TICKS = 30;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let downTicks = 0;        // consecutive ticks observed disconnected
let armedTimer = null;    // pending one-shot fallback timer
let forced = false;       // have we taken over from the server
let ticksSinceForce = 0;

// ---------------------------------------------------------------------------
// Per-device offset
//
// A fresh Math.random() alone is not enough. If a whole neighbourhood loses
// connectivity at once, those devices may also have booted at once, and
// nothing guarantees their RNGs are seeded differently. Mixing in the MAC
// gives a spread that holds even in that case; the random term then varies
// the delay between successive events on the same device.
// ---------------------------------------------------------------------------

function macOffsetSeconds() {
  let info = Shelly.getDeviceInfo();
  let mac = (info !== null && info.mac !== undefined) ? info.mac : "000000000000";
  let h = 5381;
  let i;
  for (i = 0; i < mac.length; i++) {
    // mJS: String.at(offset) returns the byte value at that offset.
    h = ((h * 33) + mac.at(i)) % 100000;
  }
  return h % SPREAD_S;
}

let MAC_OFFSET_S = macOffsetSeconds();

function fallbackDelayMs() {
  let jitter = Math.floor(Math.random() * SPREAD_S);
  let delay = (MAC_OFFSET_S + jitter) % SPREAD_S;
  return delay * 1000;
}

// ---------------------------------------------------------------------------
// Relay
// ---------------------------------------------------------------------------

function closeRelay(why) {
  print("aquacell: closing relay, reason=" + why);
  Shelly.call("Switch.Set", { id: RELAY_ID, on: true }, function (result, code, msg) {
    if (code !== 0) {
      print("aquacell: Switch.Set failed code=" + JSON.stringify(code) + " msg=" + JSON.stringify(msg));
    }
  }, null);
}

// ---------------------------------------------------------------------------
// Watchdog
// ---------------------------------------------------------------------------

function cancelArmed() {
  if (armedTimer !== null) {
    Timer.clear(armedTimer);
    armedTimer = null;
  }
}

function onLinkRestored() {
  if (downTicks > 0 || forced) {
    print("aquacell: link restored after " + JSON.stringify(downTicks) + " down ticks");
  }
  cancelArmed();
  downTicks = 0;
  ticksSinceForce = 0;
  // Deliberately do NOT open the relay here. The server owns the schedule
  // again from this point, and it will command whatever it wants on its next
  // dispatch. Opening it now could dump a tank the server has not yet
  // accounted for.
  forced = false;
}

function armFallback() {
  let delay = fallbackDelayMs();
  print("aquacell: link down, arming fallback in " + JSON.stringify(delay / 1000) + " s");
  armedTimer = Timer.set(delay, false, function () {
    armedTimer = null;
    // Re-check: the link may have come back during the delay, which is the
    // common case for a broker restart.
    if (MQTT.isConnected()) {
      print("aquacell: fallback cancelled, link back during delay");
      return;
    }
    forced = true;
    ticksSinceForce = 0;
    closeRelay("mqtt down");
  }, null);
}

function tick() {
  if (MQTT.isConnected()) {
    onLinkRestored();
    return;
  }

  downTicks = downTicks + 1;

  if (forced) {
    ticksSinceForce = ticksSinceForce + 1;
    if (ticksSinceForce >= REASSERT_EVERY_TICKS) {
      ticksSinceForce = 0;
      closeRelay("reassert while down");
    }
    return;
  }

  if (downTicks >= GRACE_TICKS && armedTimer === null) {
    armFallback();
  }
}

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

print("aquacell: fallback active, mac offset=" + JSON.stringify(MAC_OFFSET_S) +
      "s grace=" + JSON.stringify(GRACE_TICKS) + " ticks spread=" +
      JSON.stringify(SPREAD_S) + "s");

Timer.set(TICK_MS, true, tick, null);
