#!/usr/bin/env bash
#
# Generate a private CA and a broker certificate for EMQX's 8883 listener.
#
# Use this only when you have no DNS name for the server. If you do have one,
# use Let's Encrypt instead: a Shelly with ssl_ca="ca.pem" validates against its
# built-in CA bundle, so a publicly-trusted certificate needs no per-device
# setup at all. With the private CA below, every device must additionally have
# the CA uploaded (scripts/shelly_put_ca.sh) and be set to ssl_ca="user_ca.pem".
#
# Usage:
#   scripts/make_server_cert.sh <hostname-or-ip> [more-names...]
#
# Examples:
#   scripts/make_server_cert.sh mqtt.example.com
#   scripts/make_server_cert.sh 203.0.113.10
#   scripts/make_server_cert.sh mqtt.example.com 203.0.113.10
#
# The address you give here must be EXACTLY what the device connects to. A
# certificate issued for an IP will not validate when the device is pointed at
# a hostname, and vice versa — that mismatch is the most common cause of a
# silent TLS failure on these devices, because the Shelly reports only
# connected:false with no reason.

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <hostname-or-ip> [more-names...]" >&2
    exit 64
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
certs="${repo_root}/infrastructure/emqx/certs"
mkdir -p "${certs}"

DAYS_CA=3650
DAYS_SERVER=825   # browsers/libraries increasingly reject longer leaf certs

# Build the SAN list, classifying each argument as IP or DNS. Certificate
# validation uses the SAN extension, not the Common Name — a cert with only a
# CN is rejected by anything modern.
san=""
for name in "$@"; do
    if [[ "${name}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        san+="IP:${name},"
    else
        san+="DNS:${name},"
    fi
done
san="${san%,}"

PRIMARY="$1"

echo "generating CA..."
openssl genrsa -out "${certs}/ca.key" 4096 2>/dev/null
openssl req -x509 -new -nodes -sha256 \
    -key "${certs}/ca.key" \
    -days "${DAYS_CA}" \
    -subj "/CN=AquaCell Private CA/O=AquaCell" \
    -out "${certs}/ca.crt" 2>/dev/null

echo "generating broker key and CSR for ${san}..."
openssl genrsa -out "${certs}/server.key" 2048 2>/dev/null
openssl req -new -sha256 \
    -key "${certs}/server.key" \
    -subj "/CN=${PRIMARY}/O=AquaCell" \
    -out "${certs}/server.csr" 2>/dev/null

cat > "${certs}/server.ext" <<EOF
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = ${san}
EOF

echo "signing..."
openssl x509 -req -sha256 \
    -in "${certs}/server.csr" \
    -CA "${certs}/ca.crt" \
    -CAkey "${certs}/ca.key" \
    -CAcreateserial \
    -days "${DAYS_SERVER}" \
    -extfile "${certs}/server.ext" \
    -out "${certs}/server.crt" 2>/dev/null

rm -f "${certs}/server.csr" "${certs}/server.ext"

# EMQX runs as a non-root user inside the container and reads these read-only.
chmod 644 "${certs}/ca.crt" "${certs}/server.crt"
chmod 644 "${certs}/server.key"
chmod 600 "${certs}/ca.key"

echo
echo "written to infrastructure/emqx/certs/ :"
echo "  ca.crt      -> upload to each device: scripts/shelly_put_ca.sh"
echo "  ca.key      -> KEEP PRIVATE, never leaves this machine"
echo "  server.crt  -> EMQX 8883 certificate"
echo "  server.key  -> EMQX 8883 private key"
echo
echo "verify the SANs:"
openssl x509 -in "${certs}/server.crt" -noout -text \
  | grep -A1 'Subject Alternative Name' || true
echo
echo "then in .env:"
echo "  MQTT_TLS_CERTFILE=/opt/emqx/etc/certs/aquacell/server.crt"
echo "  MQTT_TLS_KEYFILE=/opt/emqx/etc/certs/aquacell/server.key"
echo "  MQTT_TLS_BIND=0.0.0.0"
echo
echo "and restart the broker:  docker compose up -d --force-recreate emqx"
