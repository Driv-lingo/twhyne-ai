#!/bin/bash
# Twhyne AI container entrypoint:
#   1. Validate the license key against the licensing API
#   2. Start the Flask backend (port 5002)
#   3. Serve the static frontend (port 3000)
set -e

echo "============================================================"
echo " Twhyne AI"
echo "============================================================"

if [ -z "$SNF_LICENSE_KEY" ]; then
    echo "ERROR: No license key provided (SNF_LICENSE_KEY)."
    exit 1
fi

API_URL="${LICENSE_API_URL:-https://twhyne.com}"

# Stable device id: persisted under the mounted rag_storage volume so it
# survives image updates; hashed with the key (raw id never leaves the box).
DEVICE_FILE="/app/backend/rag_storage/device_id"
mkdir -p "$(dirname "$DEVICE_FILE")" 2>/dev/null || true
if [ ! -s "$DEVICE_FILE" ]; then
    ( cat /etc/machine-id 2>/dev/null || hostname || echo "unknown" ) > "$DEVICE_FILE"
fi
MACHINE_ID=$(printf '%s|%s' "$(cat "$DEVICE_FILE" 2>/dev/null)" "$SNF_LICENSE_KEY" \
    | sha256sum | cut -c1-32)

echo "Validating license against $API_URL ..."
RESP=$(curl -s -X POST "$API_URL/api/validate" \
    -H "Content-Type: application/json" \
    -d "{\"license_key\":\"$SNF_LICENSE_KEY\",\"machine_id\":\"$MACHINE_ID\"}" || true)

if echo "$RESP" | grep -qE '"valid"[[:space:]]*:[[:space:]]*true'; then
    echo "License valid."
elif echo "$RESP" | grep -qE '"valid"[[:space:]]*:[[:space:]]*false'; then
    # An EXPLICIT rejection from the license server: revoked / expired /
    # unknown key. Fail closed.
    echo "ERROR: License rejected by the license server."
    echo "Response: $RESP"
    exit 1
else
    # No usable answer (offline, DNS, our web host down, an HTML error page).
    # A local-first product must not lock a customer out of their own
    # machine because OUR website is unreachable. Start anyway; the
    # runtime's own periodic heartbeat re-checks and enforces licensing
    # with the normal grace window once the server is reachable again.
    echo "WARNING: license server gave no usable answer (offline or an error page)."
    echo "Starting in local mode; licensing is re-checked by the runtime heartbeat."
    echo "Response (first 200 chars): $(printf '%s' "$RESP" | head -c 200)"
fi

# SIGNALS: this script is PID 1, and PID 1 gets no default signal handling -
# without an explicit trap, docker's forwarded Ctrl+C / docker stop is
# silently dropped and the container only dies to SIGKILL (observed as
# "Ctrl+C does not interrupt" on Linux; same on every platform).
BACKEND_PID=""
FRONTEND_PID=""
shutdown() {
    echo ""
    echo "Stopping Twhyne AI ..."
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    wait 2>/dev/null
    exit 0
}
trap shutdown INT TERM

# Start backend
echo "Starting backend on :5002 ..."
cd /app/backend
# Production images ship bytecode only (server.pyc); dev builds keep .py.
if [ -f server.pyc ]; then
    python3 server.pyc &
else
    python3 server.py &
fi
BACKEND_PID=$!

# Give the backend a moment, then serve the frontend
sleep 3
echo "Serving frontend on :3000 ..."
python3 -m http.server 3000 --directory /app/frontend/build &
FRONTEND_PID=$!

echo "============================================================"
echo " Twhyne AI is running"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:5002"
echo "============================================================"

# Exit if either process dies
wait -n "$BACKEND_PID" "$FRONTEND_PID"
