#!/bin/bash

echo "🚀 Installing SNF-AI Windsurf..."

# Create docker-compose.yml for user installation
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  snf-ai-windsurf:
    image: twhyne/twhyne:latest
    ports:
      - "3000:3000"  # Frontend
      - "5001:5001"  # Backend API  
      - "5002:5002"  # Backend API (fallback)
    volumes:
      - snf_models:/app/models      # Persist model files
      - snf_logs:/app/logs          # Persist logs
    environment:
      - NODE_ENV=production
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5002/status"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s

volumes:
  snf_models:
    driver: local
  snf_logs:
    driver: local
EOF

echo "✅ Created docker-compose.yml"
echo "🔄 Starting SNF-AI Windsurf..."

docker-compose up -d

echo ""
echo "🎉 SNF-AI Windsurf is starting up!"
echo "📊 Dashboard: http://localhost:5002/dashboard/"
echo "🔧 API: http://localhost:5002/query"
echo "📝 Status: http://localhost:5002/status"
echo ""
echo "⏳ Please wait 2-3 minutes for models to download..."
echo "📋 Check status with: docker-compose logs -f"
