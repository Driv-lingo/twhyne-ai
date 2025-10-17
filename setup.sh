#!/bin/bash

echo "🚀 Setting up SNF-AI Windsurf Clean Implementation..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required but not installed."
    exit 1
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
cd frontend
npm install
cd ..

# Make scripts executable
chmod +x scripts/*.sh

echo "✅ Setup complete!"
echo ""
echo "To start the system:"
echo "1. Backend: ./scripts/start_backend.sh"
echo "2. Frontend: ./scripts/start_frontend.sh"
echo ""
echo "Access the application at: http://localhost:3000"
