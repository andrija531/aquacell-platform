#!/usr/bin/env bash
#
# Create an MQTT credential in EMQX's built-in authentication database.
#
# Decision #53: per-device credentials, never a shared password. A homeowner
# can read their own Shelly's configuration over the local HTTP API, so one
# extracted shared credential would compromise the fleet.
#
# Usage:
#   scripts/emqx_add_user.sh <username> <password>
#   scripts/emqx_add_user.sh --list
#
# Requires EMQX_DASHBOARD_PASSWORD in the environment or in .env.

set -euo pipefail

EMQX_API="${EMQX_API:-http://127.0.0.1:18083/api/v5}"
AUTHN_ID="password_based:built_in_database"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Pull dashboard credentials from .env without exporting the whole file.
if [[ -z "${EMQX_DASHBOARD_PASSWORD:-}" && -f "${repo_root}/.env" ]]; then
    EMQX_DASHBOARD_PASSWORD="$(grep -E '^EMQX_DASHBOARD_PASSWORD=' "${repo_root}/.env" | head -1 | cut -d= -f2-)"
fi

if [[ -z "${EMQX_DASHBOARD_PASSWORD:-}" ]]; then
    echo "error: EMQX_DASHBOARD_PASSWORD not set and not found in .env" >&2
    exit 1
fi

EMQX_DASHBOARD_USER="${EMQX_DASHBOARD_USER:-admin}"

# The /api/v5 endpoints reject HTTP basic auth; they want either an API key or
# a bearer token from the dashboard login endpoint. Exchange the password for a
# short-lived token.
login_token() {
    local response
    response="$(curl -fsS -X POST "${EMQX_API}/login" \
        -H 'Content-Type: application/json' \
        --data-binary "$(printf '{"username":"%s","password":"%s"}' \
            "${EMQX_DASHBOARD_USER}" "${EMQX_DASHBOARD_PASSWORD}")")"
    python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"${response}"
}

TOKEN="$(login_token)"

if [[ "${1:-}" == "--list" ]]; then
    curl -fsS "${EMQX_API}/authentication/${AUTHN_ID}/users" \
        -H "Authorization: Bearer ${TOKEN}" \
    | python3 -c '
import json, sys
for u in json.load(sys.stdin).get("data", []):
    print(u["user_id"])'
    exit 0
fi

if [[ $# -ne 2 ]]; then
    echo "usage: $0 <username> <password>" >&2
    echo "       $0 --list" >&2
    exit 64
fi

USERNAME="$1"
PASSWORD="$2"

# jq is not assumed to be installed; python3 builds the body so the password is
# JSON-escaped rather than string-interpolated into the payload.
body="$(USERNAME="${USERNAME}" PASSWORD="${PASSWORD}" python3 -c '
import json, os
print(json.dumps({"user_id": os.environ["USERNAME"],
                  "password": os.environ["PASSWORD"]}))')"

http_code="$(curl -sS -o /tmp/emqx_add_user.out -w '%{http_code}' \
    -X POST "${EMQX_API}/authentication/${AUTHN_ID}/users" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H 'Content-Type: application/json' \
    --data-binary "${body}")"

case "${http_code}" in
    2*)
        echo "created MQTT credential: ${USERNAME}"
        ;;
    409)
        echo "credential ${USERNAME} already exists; leaving it alone" >&2
        ;;
    *)
        echo "error: EMQX returned HTTP ${http_code}" >&2
        cat /tmp/emqx_add_user.out >&2
        rm -f /tmp/emqx_add_user.out
        exit 1
        ;;
esac
rm -f /tmp/emqx_add_user.out
