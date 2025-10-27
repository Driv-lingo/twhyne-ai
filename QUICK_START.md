# SNF-AI Windsurf - Quick Start Guide

## First Time Installation

```bash
# 1. Pull the latest image
docker pull twhyne/twhyne:prod

# 2. Run the container
docker run -d \
  --name snf-ai-windsurf \
  -p 3000:3000 \
  -p 5001:5001 \
  -v snf_models:/app/models \
  -v snf_logs:/app/logs \
  twhyne/twhyne:prod
```

Access at: **http://localhost:3000**

---

## Daily Usage

### Start
```bash
docker start snf-ai-windsurf
```

### Stop
```bash
docker stop snf-ai-windsurf
```

### Restart
```bash
docker restart snf-ai-windsurf
```

### View Logs
```bash
docker logs -f snf-ai-windsurf
# Press Ctrl+C to exit logs (container keeps running)
```

### Check Status
```bash
docker ps | grep snf-ai-windsurf
```

---

## Update to Latest Version

```bash
# 1. Stop and remove old container
docker stop snf-ai-windsurf
docker rm snf-ai-windsurf

# 2. Pull latest image
docker pull twhyne/twhyne:prod

# 3. Run new container (same command as first time)
docker run -d \
  --name snf-ai-windsurf \
  -p 3000:3000 \
  -p 5001:5001 \
  -v snf_models:/app/models \
  -v snf_logs:/app/logs \
  twhyne/twhyne:prod
```

**Note:** Your models and logs are preserved in Docker volumes.

---

## Troubleshooting

### Port Already in Use
```bash
# Find what's using the ports
docker ps -a

# Stop conflicting containers
docker stop <container-name>
docker rm <container-name>
```

### Container Won't Start
```bash
# Check logs for errors
docker logs snf-ai-windsurf

# Remove and recreate
docker rm snf-ai-windsurf
# Then run the docker run command again
```

### Models Not Loading
```bash
# Models download automatically on first run
# Wait 5-10 minutes for initial download
docker logs -f snf-ai-windsurf
```

---

## Complete Cleanup

To remove everything (including downloaded models):
```bash
docker stop snf-ai-windsurf
docker rm snf-ai-windsurf
docker volume rm snf_models snf_logs
docker image rm twhyne/twhyne:prod
```

**Warning:** This deletes all downloaded models (~8GB). You'll need to download them again.
