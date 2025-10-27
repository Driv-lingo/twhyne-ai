#!/bin/bash

echo "🔄 Updating SNF-AI Windsurf Docker Image..."

# Stop and remove old container
echo "Stopping old container..."
docker stop twhyne 2>/dev/null || true
docker rm twhyne 2>/dev/null || true

# Pull latest image
echo "Pulling latest image from Docker Hub..."
docker pull twhyne/twhyne:prod

# Run new container
echo "Starting new container..."
docker run -d --name twhyne \
  -p 3000:3000 \
  -p 5001:5001 \
  -v snf_models:/app/models \
  -v snf_logs:/app/logs \
  twhyne/twhyne:prod

echo ""
echo "✅ Update complete!"
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:5001"
echo ""
echo "Check logs with: docker logs -f twhyne"
