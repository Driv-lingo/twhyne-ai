# SNF-AI Windsurf - Quick Start Guide

## First Time Installation

```bash
# 1. Pull the latest image
docker pull twhyne/twhyne:prod

# 2. Run the container
docker run -d \
  --name twhyne \
  -p 3000:3000 \
  -p 5002:5002 \
  -v snf_models:/app/models \
  -v snf_logs:/app/logs \
  twhyne/twhyne:prod
```

Access at: **http://localhost:3000**

---

## Daily Usage

### Start
```bash
docker start twhyne
```

### Stop
```bash
docker stop twhyne
```

### Restart
```bash
docker restart twhyne
```

### View Logs
```bash
docker logs -f twhyne
# Press Ctrl+C to exit logs (container keeps running)
```

### Check Status
```bash
docker ps | grep twhyne
```

---

## Update to Latest Version

```bash
# 1. Stop and remove old container
docker stop twhyne
docker rm twhyne

# 2. Pull latest image
docker pull twhyne/twhyne:prod

# 3. Run new container (same command as first time)
docker run -d \
  --name twhyne \
  -p 3000:3000 \
  -p 5002:5002 \
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
docker logs twhyne

# Remove and recreate
docker rm twhyne
# Then run the docker run command again
```

### Models Not Loading
```bash
# Models download automatically on first run
# Wait 5-10 minutes for initial download
docker logs -f twhyne
```

---

## Complete Cleanup

To remove everything (including downloaded models):
```bash
docker stop twhyne
docker rm twhyne
docker volume rm snf_models snf_logs
docker image rm twhyne/twhyne:prod
```

**Warning:** This deletes all downloaded models (~8GB). You'll need to download them again.
