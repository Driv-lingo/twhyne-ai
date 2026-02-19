# SNF-AI Windsurf - AI Assistant Platform

## 🚀 Quick Start

### Option 1: Docker Run
```bash
docker run -d \
  --name twhyne \
  -p 3000:3000 \
  -p 5002:5002 \
  -v snf_models:/app/models \
  -v snf_logs:/app/logs \
  twhyne/twhyne:prod
```

### Option 2: Docker Compose
Create a `docker-compose.yml`:
```yaml
version: '3.8'

services:
  snf-ai-windsurf:
    image: twhyne/twhyne:prod
    ports:
      - "3000:3000"  # Frontend
      - "5002:5002"  # Backend API
    volumes:
      - snf_models:/app/models
      - snf_logs:/app/logs
    restart: unless-stopped
    
volumes:
  snf_models:
  snf_logs:
```

Then run:
```bash
docker-compose up -d
```

## 🌐 Access
- **Frontend UI**: http://localhost:3000
- **API**: http://localhost:5002/query
- **Status**: http://localhost:5002/status

## 📋 Requirements
- Docker installed
- 8GB+ RAM
- 10GB free disk space

## 🔄 Update
```bash
docker pull twhyne/twhyne:prod
docker restart twhyne
```

## 🛑 Stop
```bash
docker stop twhyne
```

That's it! No GitHub, no releases, just Docker Hub.
