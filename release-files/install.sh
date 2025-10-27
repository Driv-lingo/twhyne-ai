#!/bin/bash

echo "🚀 SNF-AI Windsurf Installer"
echo "=============================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first:"
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first:"
    echo "   https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker and Docker Compose found"

# Download docker-compose.yml
echo "📥 Downloading configuration..."
curl -L -o docker-compose.yml https://github.com/Driv-lingo/twhyne-ai/releases/download/v1.0.0/docker-compose.yml

if [ $? -ne 0 ]; then
    echo "❌ Failed to download configuration file"
    exit 1
fi

echo "✅ Configuration downloaded"

# Start the application
echo "🚀 Starting SNF-AI Windsurf..."
docker-compose up -d

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 SNF-AI Windsurf is starting up!"
    echo ""
    echo "📍 Access Points:"
    echo "   🌐 Dashboard: http://localhost:5002/dashboard/"
    echo "   🔧 API: http://localhost:5002/query"
    echo "   📊 Status: http://localhost:5002/status"
    echo ""
    echo "⏳ First run takes 2-3 minutes to download AI models"
    echo "📋 Monitor progress: docker-compose logs -f"
    echo ""
    echo "🛑 To stop: docker-compose down"
else
    echo "❌ Failed to start SNF-AI Windsurf"
    exit 1
fi
