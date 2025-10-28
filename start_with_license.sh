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

# Step 2: Start the backend server
cd /app/backend
# Run server directly (app_launcher.py uses GUI which doesn't work in Docker)
python3 server.py &
BACKEND_PID=$!

# Step 3: Start the frontend server (if exists)
if [ -d "/app/frontend" ]; then
    cd /app/frontend
    if [ -f "package.json" ]; then
        npm start &
        FRONTEND_PID=$!
    fi
fi

echo ""
echo "✓ Application started successfully"
echo "============================================================"
echo "Backend PID: $BACKEND_PID"
[ ! -z "$FRONTEND_PID" ] && echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Access the application at:"
echo "  Frontend: http://localhost:3000"
echo "  Backend API: http://localhost:5002"
echo "============================================================"

# Keep the container running and handle shutdown
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGTERM SIGINT

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID
