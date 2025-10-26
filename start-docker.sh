#!/bin/bash

echo "Starting SNF-AI Windsurf Docker Container..."

# Try to download models (non-blocking if it fails)
echo "Checking for model files..."
python /app/scripts/download_models.py || echo "Model download failed, continuing with existing models..."

# Start backend server on port 5001 to match Docker port mapping
echo "Starting backend server on port 5001..."
cd /app/backend
export PORT=5001
python server.py
