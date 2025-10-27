#!/bin/bash

echo "Starting SNF-AI Windsurf Docker Container..."

# Try to download models (non-blocking if it fails)
echo "Checking for model files..."
python /app/scripts/download_models.py || echo "Model download failed, continuing with existing models..."

# Create symlinks for model files (handle different naming conventions)
echo "Setting up model file symlinks..."
cd /app/models
[ -f "codellama-7b.Q4_K_M.gguf" ] && ln -sf codellama-7b.Q4_K_M.gguf codellama-7b-q4.gguf
[ -f "mistral-7b-instruct-v0.2.Q4_K_M.gguf" ] && ln -sf mistral-7b-instruct-v0.2.Q4_K_M.gguf mistral-7b-instruct-q4.gguf
echo "Model symlinks created."

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
