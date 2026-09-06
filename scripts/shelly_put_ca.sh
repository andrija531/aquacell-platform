#!/usr/bin/env bash
#
# Upload a CA certificate to a Shelly so it can validate a broker certificate
# that is not signed by a publicly-trusted authority.
#
# Only needed with a private CA (scripts/make_server_cert.sh). With a Let's
# Encrypt certificate the device's built-in bundle already covers it and you
# should use ssl_ca="ca.pem" instead — skip this script entirely.
#
# Usage:
#   scripts/shelly_put_ca.sh <shelly-ip> [ca-file]
#   scripts/shelly_put_ca.sh <shelly-ip> --clear
#
# Default ca-file is infrastructure/emqx/certs/ca.crt.
#
# Shelly.PutUserCA takes the PEM in chunks: the first call with append=false
# replaces whatever was there, subsequent calls with append=true extend it.
# Chunks must be small — the device has very little RAM and rejects or drops
# large request bodies.
#
# NOTE: this follows the documented RPC interface but has not been run against
# hardware. If it fails, the same thing is achievable through the device web UI.

set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "usage: $0 <shelly-ip> [ca-file|--clear]" >&2
    exit 64
fi

SHELLY_IP="$1"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CA_FILE="${2:-${repo_root}/infrastructure/emqx/certs/ca.crt}"

CHUNK_BYTES="${CHUNK_BYTES:-512}"

rpc() {
    curl -fsS --max-time 15 -X POST \
        -H 'Content-Type: application/json' \
        --data-binary "$1" \
        "http://${SHELLY_IP}/rpc"
}

if [[ "${2:-}" == "--clear" ]]; then
    echo "clearing user CA on ${SHELLY_IP}..."
    rpc '{"id":1,"method":"Shelly.PutUserCA","params":{"data":null,"append":false}}'
    echo
    exit 0
fi

if [[ ! -f "${CA_FILE}" ]]; then
    echo "error: ${CA_FILE} not found. Run scripts/make_server_cert.sh first." >&2
    exit 1
fi

echo "uploading ${CA_FILE} to ${SHELLY_IP} in ${CHUNK_BYTES}-byte chunks..."

# python3 does the chunking and JSON escaping: a PEM contains newlines, which
# must be encoded rather than interpolated into the request body.
CA_FILE="${CA_FILE}" CHUNK_BYTES="${CHUNK_BYTES}" SHELLY_IP="${SHELLY_IP}" python3 - <<'PY'
import json, os, sys, urllib.request

ca_path = os.environ["CA_FILE"]
chunk_size = int(os.environ["CHUNK_BYTES"])
url = f"http://{os.environ['SHELLY_IP']}/rpc"

pem = open(ca_path, "r", encoding="ascii").read()
chunks = [pem[i:i + chunk_size] for i in range(0, len(pem), chunk_size)]

def call(payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

for i, chunk in enumerate(chunks):
    result = call({
        "id": i + 1,
        "method": "Shelly.PutUserCA",
        "params": {"data": chunk, "append": i > 0},
    })
    if "error" in result:
        print(f"chunk {i + 1}/{len(chunks)} failed: {result['error']}", file=sys.stderr)
        sys.exit(1)
    print(f"chunk {i + 1}/{len(chunks)} ok", flush=True)

print("upload complete")
PY

echo
echo "now point the device at the broker over TLS:"
echo "  SHELLY_TLS=user_ca scripts/shelly_provision.sh ${SHELLY_IP} <broker-host> '<password>' 8883"
