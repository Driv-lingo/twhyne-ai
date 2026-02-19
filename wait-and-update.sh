#!/bin/bash

echo "🔄 Waiting for Multi-Platform Docker Build to Complete..."
echo ""
echo "The GitHub Actions workflow is building for:"
echo "  • linux/amd64 (Intel/AMD PCs)"
echo "  • linux/arm64 (Apple Silicon Macs)"
echo ""
echo "This will take approximately 20-30 minutes."
echo ""
echo "Check build status at:"
echo "https://github.com/Driv-lingo/twhyne-ai/actions"
echo ""

read -p "Press Enter when the build is complete (green checkmark)..."

echo ""
echo "🎯 Pulling latest multi-platform image..."
docker pull twhyne/twhyne:prod

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Image pulled successfully!"
    echo ""
    echo "🛑 Stopping old containers..."
    docker stop twhyne 2>/dev/null || true
    docker rm twhyne 2>/dev/null || true
    
    echo ""
    echo "🚀 Starting new container with fixed ports..."
    docker run -d --name twhyne \
      -p 3000:3000 \
      -p 5002:5002 \
      -v snf_models:/app/models \
      -v snf_logs:/app/logs \
      twhyne/twhyne:prod
    
    echo ""
    echo "✅ Container started successfully!"
    echo ""
    echo "📍 Access URLs:"
    echo "   Frontend: http://localhost:3000"
    echo "   Backend:  http://localhost:5002"
    echo ""
    echo "📋 Useful commands:"
    echo "   View logs:    docker logs -f twhyne"
    echo "   Stop:         docker stop twhyne"
    echo "   Restart:      docker restart twhyne"
else
    echo ""
    echo "❌ Pull failed. The build may not be complete yet."
    echo "   Check: https://github.com/Driv-lingo/twhyne-ai/actions"
fi
