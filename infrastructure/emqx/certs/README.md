Broker TLS certificates are mounted from this directory into EMQX at
/opt/emqx/etc/certs/aquacell.

Nothing here is committed — the contents are gitignored, because certificates
are per-host and private keys must never enter a repository.

Two ways to populate it:

1. Let's Encrypt, if the server has a DNS name. Preferred: a Shelly with
   ssl_ca="ca.pem" validates against its built-in CA bundle, so devices need
   no extra setup. Copy or symlink fullchain.pem and privkey.pem here after
   certbot issues them, and make them readable by the container.

2. scripts/make_server_cert.sh, if you only have an IP. Generates a private CA
   plus a broker certificate. Every device then needs the CA uploaded via
   scripts/shelly_put_ca.sh and ssl_ca="user_ca.pem".

Point .env at whichever you used:

    MQTT_TLS_CERTFILE=/opt/emqx/etc/certs/aquacell/<cert>
    MQTT_TLS_KEYFILE=/opt/emqx/etc/certs/aquacell/<key>

See docs/06-shelly-poc-runbook.md.
