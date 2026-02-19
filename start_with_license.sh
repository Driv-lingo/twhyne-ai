#!/bin/bash
# SNF-AI Windsurf - Startup script with license enforcement

set -e

echo "============================================================"
echo "SNF-AI Windsurf - Starting"
echo "============================================================"

# Step 1: Check license FIRST
echo ""
echo "Step 1: Validating license..."
python3 /app/backend/simple_license_check.py

# If license check fails, the script exits here (due to set -e)
# If we get here, license is valid

echo ""
echo "Step 2: Starting application..."
echo "============================================================"

# Step 2: Start the backend server (also serves frontend static files)
cd /app/backend
python3 server.py &
BACKEND_PID=$!

echo ""
echo "✓ Application started successfully"
echo "============================================================"
echo "Backend PID: $BACKEND_PID"
echo ""
echo "Access the application at:"
echo "  Application: http://localhost:${PORT:-5002}"
echo "  Backend API: http://localhost:${PORT:-5002}/status"
echo "============================================================"

# Keep the container running and handle shutdown
trap "kill $BACKEND_PID 2>/dev/null; exit" SIGTERM SIGINT

# Wait for backend process
wait $BACKEND_PID
