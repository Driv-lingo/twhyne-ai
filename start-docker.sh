#!/bin/bash

echo "Starting SNF-AI Windsurf Docker Container..."

# Try to download models (non-blocking if it fails)
echo "Checking for model files..."
python /app/scripts/download_models.py || echo "Model download failed, continuing with existing models..."

# Start frontend server in background
echo "Starting frontend server on port 3000..."
cd /app/frontend/build
python3 -m http.server 3000 &
FRONTEND_PID=$!

# Start backend server
echo "Starting backend server on port 5001..."
cd /app/backend
export PORT=5001
python server.py
