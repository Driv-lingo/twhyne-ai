# 🚀 SNF-AI Windsurf - One-Command Installation

## Quick Install

**Step 1:** Create the Docker Compose file:

```bash
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
```

**Step 2:** Start the application:

```bash
docker-compose up -d
```

## 🎯 Access Points

- **Dashboard**: http://localhost:5002/dashboard/
- **API**: http://localhost:5002/query  
- **Status**: http://localhost:5002/status

## ⏳ First Run

The first startup takes 2-3 minutes to download AI models (~8GB). Monitor progress with:

```bash
docker-compose logs -f
```

## 🛑 Stop/Remove

```bash
docker-compose down
docker-compose down -v  # Remove data volumes too
```
