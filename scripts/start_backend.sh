#!/bin/bash

# Start the backend server
echo "🚀 Starting SNF-AI Windsurf Backend Server..."
cd "$(dirname "$0")/../backend"
python3 server.py
