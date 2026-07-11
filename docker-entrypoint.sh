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
echo "Validating license against $API_URL ..."
RESP=$(curl -s -X POST "$API_URL/api/validate" \
    -H "Content-Type: application/json" \
    -d "{\"license_key\":\"$SNF_LICENSE_KEY\"}" || true)

if echo "$RESP" | grep -qE '"valid"[[:space:]]*:[[:space:]]*true'; then
    echo "License valid."
else
    echo "ERROR: License validation failed."
    echo "Response: $RESP"
    exit 1
fi

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
