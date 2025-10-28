# SNF-AI Windsurf - Simple Installation

## Windows (Easy Way)

**1. Install Docker Desktop**
- Download: https://www.docker.com/products/docker-desktop/
- Install and restart computer

**2. Download installer**
- Download: `customer-install.ps1`

**3. Run installer (Right-click PowerShell as Admin)**
```powershell
.\customer-install.ps1
```

**4. Enter your license key when prompted**

**5. Done! Open: http://localhost:3000**

---

## Mac (Easy Way)

**1. Install Docker Desktop**
- Download: https://www.docker.com/products/docker-desktop/
- Install and open

**2. Download installer**
- Download: `customer-install.sh`

**3. Run installer in Terminal**
```bash
chmod +x customer-install.sh
./customer-install.sh
```

**4. Enter your license key when prompted**

**5. Done! Open: http://localhost:3000**

---

## Manual Installation (All Platforms)

**One command - that's it:**

**Windows (PowerShell):**
```powershell
docker run -d --name twhyne -e SNF_LICENSE_KEY="YOUR-KEY-HERE" -p 3000:3000 -p 5001:5001 --mount source=snf_models,target=/app/models --mount source=snf_logs,target=/app/logs --restart unless-stopped twhyne/twhyne:prod
```

**Mac/Linux (Terminal):**
```bash
docker run -d --name twhyne -e SNF_LICENSE_KEY="YOUR-KEY-HERE" -p 3000:3000 -p 5001:5001 --mount source=snf_models,target=/app/models --mount source=snf_logs,target=/app/logs --restart unless-stopped twhyne/twhyne:prod
```

Replace `YOUR-KEY-HERE` with your actual license key.

---

## Access

**Open browser:** http://localhost:3000

---

## Common Commands

```bash
# View logs
docker logs -f twhyne

# Stop
docker stop twhyne

# Start
docker start twhyne

# Restart
docker restart twhyne

# Remove
docker rm -f twhyne

# Update to latest version
docker pull twhyne/twhyne:prod
docker rm -f twhyne
# Then run the install command again
```

---

## License Expired?

1. Visit: https://sunny-imagination-production.up.railway.app
2. Purchase new license
3. Stop old container: `docker rm -f twhyne`
4. Run with new license key

---

## Support

**License Portal:** https://sunny-imagination-production.up.railway.app  
**Email:** support@twhyne.com

**That's it - no complex setup needed!** 🚀
