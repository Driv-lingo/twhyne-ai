#!/bin/bash
# Twhyne AI - macOS/Linux Launcher

set -e

echo "============================================================"
echo " Twhyne AI - Launcher"
echo "============================================================"
echo ""

# ── License key ───────────────────────────────────────────────
if [ -z "$SNF_LICENSE_KEY" ]; then
    read -rp "Enter your Twhyne license key (TWHYNE-...): " SNF_LICENSE_KEY
fi

if [ -z "$SNF_LICENSE_KEY" ]; then
    echo "ERROR: No license key provided."
    echo "Get a license at https://twhyne.com"
    read -rp "Press Enter to exit..."
    exit 1
fi

# ── Check Docker is running ───────────────────────────────────
if ! docker version > /dev/null 2>&1; then
    echo "ERROR: Docker is not running."
    echo "Please start Docker Desktop and try again."
    read -rp "Press Enter to exit..."
    exit 1
fi

# ── Pull latest image ─────────────────────────────────────────
echo "Checking for updates..."
docker pull --platform linux/arm64 twhyne/twhyne:licensed
echo ""

# ── Stop any existing container ───────────────────────────────
docker stop twhyne-ai 2>/dev/null || true
docker rm   twhyne-ai 2>/dev/null || true

# ── Write patched app_launcher.py (starts backend + serves frontend) ──
PATCH_DIR="$(mktemp -d)"
cat > "$PATCH_DIR/app_launcher.py" <<'PYEOF'
import subprocess, threading, time

def start_backend():
    subprocess.run(["python3", "server.py"], cwd="/app/backend")

def serve_frontend():
    subprocess.run(["python3", "-m", "http.server", "3000",
                    "--directory", "/app/frontend/build"])

threading.Thread(target=start_backend, daemon=True).start()
time.sleep(3)
threading.Thread(target=serve_frontend, daemon=True).start()

while True:
    time.sleep(60)
PYEOF

# ── Open browser once the frontend is up ─────────────────────
(sleep 15 && open "http://localhost:3000" 2>/dev/null || xdg-open "http://localhost:3000" 2>/dev/null || true) &

# ── Launch ────────────────────────────────────────────────────
echo "Starting Twhyne AI..."
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:5002"
echo ""
echo "Press Ctrl+C to stop."
echo "============================================================"

docker run --name twhyne-ai --rm \
  --platform linux/arm64 \
  -e SNF_LICENSE_KEY="$SNF_LICENSE_KEY" \
  -e LICENSE_API_URL=https://twhyne.com \
  -e SNF_LICENSE_API=https://twhyne.com \
  -v "$PATCH_DIR/app_launcher.py:/app/backend/app_launcher.py:ro" \
  -p 3000:3000 \
  -p 5002:5002 \
  twhyne/twhyne:licensed

rm -rf "$PATCH_DIR"
