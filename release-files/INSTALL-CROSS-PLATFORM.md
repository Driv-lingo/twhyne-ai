# 🚀 SNF-AI Windsurf - Cross-Platform Installation

## 🖥️ Windows Installation

### Option 1: One-Click Installer
1. Download and run: [`install-windows.bat`](https://github.com/Driv-lingo/twhyne-ai/releases/download/v1.0.0/install-windows.bat)
2. Right-click → "Run as administrator" (if needed)

### Option 2: Manual Installation
```cmd
# Download configuration
curl -L -o docker-compose.yml https://github.com/Driv-lingo/twhyne-ai/releases/download/v1.0.0/docker-compose.yml

# Start application
docker-compose up -d
```

### Prerequisites (Windows):
- **Docker Desktop for Windows**: https://docs.docker.com/desktop/windows/
- **Windows 10/11** with WSL2 enabled
- **8GB RAM minimum**

---

## 🍎 macOS Installation

### Option 1: One-Click Installer
```bash
curl -L https://github.com/Driv-lingo/twhyne-ai/releases/download/v1.0.0/install.sh | bash
```

### Option 2: Manual Installation
```bash
# Download configuration
curl -L -o docker-compose.yml https://github.com/Driv-lingo/twhyne-ai/releases/download/v1.0.0/docker-compose.yml

# Start application
docker-compose up -d
```

### Prerequisites (macOS):
- **Docker Desktop for Mac**: https://docs.docker.com/desktop/mac/
- **macOS 10.15+** (Catalina or newer)
- **8GB RAM minimum**

---

## 🐧 Linux Installation

### Option 1: One-Click Installer
```bash
curl -L https://github.com/Driv-lingo/twhyne-ai/releases/download/v1.0.0/install.sh | bash
```

### Option 2: Manual Installation
```bash
# Download configuration
curl -L -o docker-compose.yml https://github.com/Driv-lingo/twhyne-ai/releases/download/v1.0.0/docker-compose.yml

# Start application
docker-compose up -d
```

### Prerequisites (Linux):
- **Docker Engine**: https://docs.docker.com/engine/install/
- **Docker Compose**: https://docs.docker.com/compose/install/
- **8GB RAM minimum**

---

## 🌐 Access Points (All Platforms)

Once installed, access the platform at:
- **🌐 Dashboard**: http://localhost:5002/dashboard/
- **🔧 API**: http://localhost:5002/query
- **📊 Status**: http://localhost:5002/status

## 🔧 Common Commands (All Platforms)

**View logs:**
```bash
docker-compose logs -f
```

**Stop application:**
```bash
docker-compose down
```

**Update to latest:**
```bash
docker-compose pull && docker-compose up -d
```

## 🚨 Troubleshooting

### Windows Issues:
- Enable WSL2 if Docker fails to start
- Run PowerShell/CMD as Administrator
- Check Windows Defender firewall settings

### macOS Issues:
- Allow Docker Desktop in System Preferences → Security
- Increase Docker Desktop memory allocation to 8GB+

### Linux Issues:
- Add user to docker group: `sudo usermod -aG docker $USER`
- Restart after adding to docker group

### All Platforms:
- **Port conflicts**: Change ports in docker-compose.yml if 5002 is in use
- **Memory issues**: Ensure 8GB+ RAM available
- **Disk space**: Need 10GB+ free for AI models
