# SNF-AI Windsurf - Quick Install (One Page)

## Windows Installation (5 minutes)

**1. Install Docker Desktop**
```
Download: https://www.docker.com/products/docker-desktop/
Run installer → Enable WSL 2 → Restart computer
```

**2. Get License Key**
```
Visit: https://sunny-imagination-production.up.railway.app
Register → Purchase ($20) → Copy license key
```

**3. Run These Commands (PowerShell)**
```powershell
# Create folder
New-Item -ItemType Directory -Path "C:\SNF-AI" -Force
cd C:\SNF-AI

# Set license key (replace with yours)
$env:SNF_LICENSE_KEY="SNF-XXXXXXXX-XXXXXXXX"

# Download and start
curl -o docker-compose.yml https://raw.githubusercontent.com/Driv-lingo/twhyne-ai/prod/docker-compose.licensed.yml
docker-compose up -d
```

**4. Access Application**
```
Open browser: http://localhost:3000
```

---

## Mac Installation (5 minutes)

**1. Install Docker Desktop**
```
Download: https://www.docker.com/products/docker-desktop/
Open .dmg → Drag to Applications → Open Docker
```

**2. Get License Key**
```
Visit: https://sunny-imagination-production.up.railway.app
Register → Purchase ($20) → Copy license key
```

**3. Run These Commands (Terminal)**
```bash
# Create folder
mkdir -p ~/SNF-AI
cd ~/SNF-AI

# Set license key (replace with yours)
export SNF_LICENSE_KEY="SNF-XXXXXXXX-XXXXXXXX"

# Download and start
curl -o docker-compose.yml https://raw.githubusercontent.com/Driv-lingo/twhyne-ai/prod/docker-compose.licensed.yml
docker-compose up -d
```

**4. Access Application**
```
Open browser: http://localhost:3000
```

---

## Manual Setup (If curl doesn't work)

**Create `docker-compose.yml` file:**

```yaml
version: '3.8'

services:
  snf-ai:
    image: twhyne/twhyne:prod
    container_name: snf-ai-windsurf
    
    environment:
      - SNF_LICENSE_KEY=SNF-XXXXXXXX-XXXXXXXX  # Your key here
      - LICENSE_API_URL=https://sunny-imagination-production.up.railway.app
    
    ports:
      - "5002:5002"
      - "3000:3000"
    
    volumes:
      - snf-models:/app/models
      - snf-data:/app/data
    
    restart: unless-stopped

volumes:
  snf-models:
  snf-data:
```

**Then run:**
- Windows: `docker-compose up -d`
- Mac: `docker-compose up -d`

---

## Common Commands

| Action | Command |
|--------|---------|
| **Start** | `docker-compose up -d` |
| **Stop** | `docker-compose down` |
| **View Logs** | `docker logs -f snf-ai-windsurf` |
| **Update** | `docker-compose pull && docker-compose up -d` |

---

## Troubleshooting

**License failed?**
- Check key is correct
- Verify not expired (30 days)
- Renew at: https://sunny-imagination-production.up.railway.app

**Port conflict?**
- Change `3000:3000` to `3001:3000` in docker-compose.yml
- Access at http://localhost:3001

**Docker not starting?**
- Open Docker Desktop and wait for it to start
- Restart computer if needed

---

## Support
- **License Portal**: https://sunny-imagination-production.up.railway.app
- **Email**: support@twhyne.com

**That's it! Your AI platform is running locally. 🚀**
