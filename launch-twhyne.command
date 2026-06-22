#!/bin/bash
# Twhyne AI - macOS Launcher
# Double-click this file to start Twhyne AI.

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

# ── Open browser after a short delay ─────────────────────────
(sleep 8 && open "http://localhost:3000") &

# ── Launch ────────────────────────────────────────────────────
echo "Starting Twhyne AI..."
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:5001"
echo ""
echo "Press Ctrl+C to stop."
echo "============================================================"

docker run --name twhyne-ai --rm \
  --platform linux/arm64 \
  -e SNF_LICENSE_KEY="$SNF_LICENSE_KEY" \
  -e LICENSE_API_URL=https://twhyne.com \
  -e SNF_LICENSE_API=https://twhyne.com \
  -p 3000:3000 \
  -p 5001:5001 \
  twhyne/twhyne:licensed
