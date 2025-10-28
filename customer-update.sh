#!/bin/bash
# SNF-AI Windsurf - Update Script for Customers

set -e

echo "🔄 SNF-AI Windsurf Update Tool"
echo "================================"
echo ""

# Check if container is running
if docker ps | grep -q twhyne; then
    echo "⚠️  SNF-AI is currently running"
    read -p "Stop and update? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Update cancelled"
        exit 1
    fi
    
    echo "Stopping current container..."
    docker stop twhyne
    docker rm twhyne
fi

# Get current version (if exists)
CURRENT_VERSION=$(docker images twhyne/twhyne --format "{{.Tag}}" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | head -1)
if [ ! -z "$CURRENT_VERSION" ]; then
    echo "Current version: $CURRENT_VERSION"
fi

# Pull latest version
echo ""
echo "📥 Downloading latest version..."
docker pull twhyne/twhyne:latest

# Get new version
NEW_VERSION=$(docker inspect twhyne/twhyne:latest --format='{{.Config.Labels.version}}' 2>/dev/null || echo "latest")
echo "New version: $NEW_VERSION"

# Check for license key
if [ -z "$SNF_LICENSE_KEY" ]; then
    echo ""
    echo "⚠️  No license key found in environment"
    read -p "Enter your license key: " LICENSE_KEY
    export SNF_LICENSE_KEY="$LICENSE_KEY"
fi

# Start updated container
echo ""
echo "🚀 Starting updated SNF-AI..."
docker run -d \
  --name twhyne \
  -e SNF_LICENSE_KEY="$SNF_LICENSE_KEY" \
  -p 3000:3000 \
  -p 5001:5001 \
  --mount source=snf_models,target=/app/models \
  --mount source=snf_logs,target=/app/logs \
  --mount source=snf_data,target=/app/data \
  --mount source=snf_uploads,target=/app/uploads \
  --mount source=snf_rag,target=/app/rag_storage \
  --mount source=snf_conversations,target=/app/conversations \
  --restart unless-stopped \
  twhyne/twhyne:latest

echo ""
echo "✅ Update complete!"
echo ""
echo "Access your updated application at:"
echo "  http://localhost:3000"
echo ""
echo "View logs: docker logs -f twhyne"
