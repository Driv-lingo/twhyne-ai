# Twhyne hosted test instance (freelancer black-box testing)

Give testers a URL, never the image. This runs the real product on a machine
you control; testers interact only through the web UI.

## Why this exists
Shipping the Docker image to an untrusted tester exposes the (bytecode)
application to inspection. Hosted access keeps the crown jewels on your box.
Bytecode stripping and native compilation raise the cost of inspection for
*customers* who legitimately hold the image; they are not a substitute for
withholding the image from anonymous testers.

## Run
    export SNF_LICENSE_KEY=TWHYNE-....
    export TWHYNE_ADMIN_TOKEN=$(openssl rand -hex 32)
    export TWHYNE_IDENTITY_SECRET=$(openssl rand -hex 32)
    docker compose up -d

Put a TLS reverse proxy (Caddy/nginx) in front of :3000; do not expose the
ports publicly as-is. Add per-tester basic-auth at the proxy.

## Give each tester a scoped identity
Signed identity is REQUIRED here, so mint a token per tester at the role you
want them to test as (they cannot escalate past it):

    curl -s -X POST http://127.0.0.1:5002/api/identity/token \
      -H "X-Admin-Token: $TWHYNE_ADMIN_TOKEN" \
      -H 'Content-Type: application/json' \
      -d '{"subject":"tester-01","role":"staff"}'

Hand the returned token to the tester; the UI sends it as a Bearer token.

## After the engagement
Rotate TWHYNE_IDENTITY_SECRET (invalidates every issued token at once),
`docker compose down`, and wipe ./test-corpus. Revoke the license key in the
admin console if the tester had one.

## Boundaries to state in the posting
Product/AI-behavior testing only. No access to servers, source, other
accounts, credentials, or infrastructure. Security intrusion is out of scope.
