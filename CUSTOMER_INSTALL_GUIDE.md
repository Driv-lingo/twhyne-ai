# SNF-AI Windsurf - Installation Guide

## 📋 Prerequisites

### Windows
- **Docker Desktop for Windows** (Download: https://www.docker.com/products/docker-desktop/)
- Windows 10/11 Pro, Enterprise, or Education (64-bit)
- WSL 2 enabled
- At least 8GB RAM

### Mac
- **Docker Desktop for Mac** (Download: https://www.docker.com/products/docker-desktop/)
- macOS 11 or later
- At least 8GB RAM

---

## 🚀 Installation Instructions

### Step 1: Install Docker Desktop

**Windows:**
1. Download Docker Desktop from https://www.docker.com/products/docker-desktop/
2. Run the installer
3. Follow prompts (enable WSL 2 when asked)
4. Restart your computer
5. Open Docker Desktop and wait for it to start

**Mac:**
1. Download Docker Desktop from https://www.docker.com/products/docker-desktop/
2. Open the `.dmg` file
3. Drag Docker to Applications folder
4. Open Docker from Applications
5. Grant permissions when prompted

**Verify Installation:**
```bash
docker --version
```
Should show: `Docker version XX.XX.XX`

---

### Step 2: Get Your License Key

1. Visit: https://sunny-imagination-production.up.railway.app
2. Register an account
3. Purchase a license ($20 for 30 days)
4. Copy your license key: `SNF-XXXXXXXX-XXXXXXXX`

---

### Step 3: Download Installation Files

**Option A: Direct Download**

Download `docker-compose.licensed.yml` from your provider, or create it:

**Windows (PowerShell):**
```powershell
# Create a folder
New-Item -ItemType Directory -Path "C:\SNF-AI" -Force
cd C:\SNF-AI

# Create docker-compose.yml file
@"
version: '3.8'

services:
  snf-ai:
    image: twhyne/twhyne:prod
    container_name: snf-ai-windsurf
    
    environment:
      - SNF_LICENSE_KEY=YOUR_LICENSE_KEY_HERE
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
"@ | Out-File -FilePath docker-compose.yml -Encoding UTF8
```

**Mac/Linux (Terminal):**
```bash
# Create a folder
mkdir -p ~/SNF-AI
cd ~/SNF-AI

# Create docker-compose.yml file
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  snf-ai:
    image: twhyne/twhyne:prod
    container_name: snf-ai-windsurf
    
    environment:
      - SNF_LICENSE_KEY=YOUR_LICENSE_KEY_HERE
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
EOF
```

---

### Step 4: Configure Your License Key

**Windows (PowerShell):**
```powershell
# Open the file in Notepad
notepad docker-compose.yml

# Replace YOUR_LICENSE_KEY_HERE with your actual key
# Save and close
```

**Mac (Terminal):**
```bash
# Edit the file
nano docker-compose.yml

# Replace YOUR_LICENSE_KEY_HERE with your actual key
# Press Ctrl+X, then Y, then Enter to save
```

**Or use environment variable (recommended):**

**Windows (PowerShell):**
```powershell
$env:SNF_LICENSE_KEY="SNF-XXXXXXXX-XXXXXXXX"
```

**Mac/Linux (Terminal):**
```bash
export SNF_LICENSE_KEY="SNF-XXXXXXXX-XXXXXXXX"
```

Then modify `docker-compose.yml` to use:
```yaml
environment:
  - SNF_LICENSE_KEY=${SNF_LICENSE_KEY}
```

---

### Step 5: Start SNF-AI Windsurf

**Windows (PowerShell):**
```powershell
cd C:\SNF-AI
docker-compose up -d
```

**Mac/Linux (Terminal):**
```bash
cd ~/SNF-AI
docker-compose up -d
```

**First-time download will take 5-10 minutes** (downloading 3.2GB image)

**Expected Output:**
```
[+] Running 3/3
 ✔ Network snf-ai_default        Created
 ✔ Volume "snf-ai_snf-models"    Created
 ✔ Volume "snf-ai_snf-data"      Created
 ✔ Container snf-ai-windsurf     Started
```

---

### Step 6: Verify Installation

**Check if running:**

**Windows (PowerShell):**
```powershell
docker ps
```

**Mac/Linux (Terminal):**
```bash
docker ps
```

Should show:
```
CONTAINER ID   IMAGE                  STATUS         PORTS
xxxxx          twhyne/twhyne:prod    Up 2 minutes   0.0.0.0:3000->3000/tcp, 0.0.0.0:5002->5002/tcp
```

**View logs:**
```bash
docker logs snf-ai-windsurf
```

Should see:
```
✓ License valid until: 2025-XX-XX
✓ License validation successful!
✓ Periodic license check enabled (every 24h)
Starting backend server...
Starting frontend server...
```

---

### Step 7: Access SNF-AI Windsurf

**Open your browser and go to:**
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:5002

---

## 🔧 Common Commands

### View Logs
```bash
docker logs -f snf-ai-windsurf
```

### Stop the Application
```bash
docker-compose down
```

### Restart the Application
```bash
docker-compose restart
```

### Update to Latest Version
```bash
docker-compose pull
docker-compose up -d
```

### Remove Everything (including data)
```bash
docker-compose down -v
```

---

## ❓ Troubleshooting

### "License validation failed"
**Problem:** License key is invalid or expired

**Solution:**
1. Check your license key is correct
2. Verify license hasn't expired (30 days)
3. Renew license at: https://sunny-imagination-production.up.railway.app
4. Update `docker-compose.yml` with new key
5. Restart: `docker-compose restart`

### "Port already in use"
**Problem:** Ports 3000 or 5002 are already used

**Solution:** Change ports in `docker-compose.yml`:
```yaml
ports:
  - "3001:3000"  # Use 3001 instead of 3000
  - "5003:5002"  # Use 5003 instead of 5002
```

Then access at: http://localhost:3001

### "Cannot connect to Docker daemon"
**Problem:** Docker Desktop is not running

**Solution:**
1. Open Docker Desktop
2. Wait for it to fully start
3. Try again

### Container keeps restarting
**Problem:** Application crashed

**Solution:**
```bash
# View logs to see error
docker logs snf-ai-windsurf

# Common issues:
# - License expired → Renew license
# - Out of memory → Close other apps, increase Docker memory
# - Missing models → Will download on first run
```

---

## 📊 System Requirements

### Minimum:
- **RAM**: 8GB
- **Storage**: 10GB free space
- **Internet**: Required for initial download and license validation

### Recommended:
- **RAM**: 16GB+
- **Storage**: 20GB+ free space
- **CPU**: 4+ cores

---

## 🔄 Updating Your License

When your 30-day license expires:

1. Visit: https://sunny-imagination-production.up.railway.app
2. Login to your account
3. Purchase new license
4. Copy new license key
5. Update `docker-compose.yml` or environment variable
6. Restart: `docker-compose restart`

---

## 📞 Support

- **License Issues**: https://sunny-imagination-production.up.railway.app
- **Documentation**: [Your support URL]
- **Email**: support@twhyne.com

---

## 📝 Quick Reference

### Windows Commands
```powershell
# Navigate to folder
cd C:\SNF-AI

# Start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker logs -f snf-ai-windsurf

# Update
docker-compose pull && docker-compose up -d
```

### Mac Commands
```bash
# Navigate to folder
cd ~/SNF-AI

# Start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker logs -f snf-ai-windsurf

# Update
docker-compose pull && docker-compose up -d
```

---

## ✅ Installation Complete!

Your SNF-AI Windsurf platform is now running locally on your machine.

**Access it at:** http://localhost:3000

**Your data stays private** - everything runs on your computer, only license validation contacts our servers.

Enjoy! 🚀
