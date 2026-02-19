#!/bin/bash
# SNF-AI Windsurf - Customer Installation Script

set -e

echo "🚀 SNF-AI Windsurf Installation"
echo "================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker Desktop first:"
    echo "   https://www.docker.com/products/docker-desktop/"
    exit 1
fi

echo "✓ Docker found"

# Get license key
read -p "Enter your license key (SNF-XXXXXXXX-XXXXXXXX): " LICENSE_KEY

if [ -z "$LICENSE_KEY" ]; then
    echo "❌ License key required"
    exit 1
fi

echo ""
echo "📥 Pulling SNF-AI Windsurf image..."
docker pull twhyne/twhyne:prod

echo ""
echo "🚀 Starting SNF-AI Windsurf..."
docker run -d \
  --name twhyne \
  -e SNF_LICENSE_KEY="$LICENSE_KEY" \
  -p 3000:3000 \
  -p 5002:5002 \
  --mount source=snf_models,target=/app/models \
  --mount source=snf_logs,target=/app/logs \
  --mount source=snf_data,target=/app/data \
  --mount source=snf_uploads,target=/app/uploads \
  --mount source=snf_rag,target=/app/rag_storage \
  --mount source=snf_conversations,target=/app/conversations \
  --restart unless-stopped \
  twhyne/twhyne:licensed

echo ""
echo "✅ Installation complete!"
echo ""
echo "🌐 Access your application at:"
echo "   http://localhost:3000"
echo ""
echo "📋 Useful commands:"
echo "   View logs:    docker logs -f twhyne"
echo "   Stop:         docker stop twhyne"
echo "   Start:        docker start twhyne"
echo "   Remove:       docker rm -f twhyne"
echo ""
