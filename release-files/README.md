# 🚀 SNF-AI Windsurf - AI Assistant Platform

A powerful AI assistant platform with multiple specialized nodes for different tasks.

## ⚡ Quick Start

**Prerequisites:** Docker and Docker Compose installed

**1. Download the installation file:**
```bash
curl -O https://github.com/Driv-lingo/twhyne-ai/releases/download/v1.0.0/docker-compose.yml
```

**2. Start the application:**
```bash
docker-compose up -d
```

**3. Access the platform:**
- 🌐 **Dashboard**: http://localhost:5002/dashboard/
- 🔧 **API Endpoint**: http://localhost:5002/query
- 📊 **Status Check**: http://localhost:5002/status

## 🤖 AI Capabilities

- **💬 Language Processing**: Natural language understanding and generation
- **💻 Code Generation**: Programming assistance and code completion  
- **🧮 Mathematical Solving**: Complex problem solving and calculations
- **👁️ Vision Analysis**: Image processing and visual understanding
- **📋 Task Planning**: Intelligent task decomposition and planning

## ⏳ First Run

Initial startup takes 2-3 minutes to download AI models (~8GB). Monitor progress:

```bash
docker-compose logs -f snf-ai-windsurf
```

## 🛠️ Management Commands

**View logs:**
```bash
docker-compose logs -f
```

**Stop application:**
```bash
docker-compose down
```

**Update to latest version:**
```bash
docker-compose pull
docker-compose up -d
```

**Remove all data:**
```bash
docker-compose down -v
```

## 📋 System Requirements

- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 10GB free space for models
- **CPU**: Multi-core processor recommended
- **OS**: Linux, macOS, or Windows with Docker

## 🔧 Configuration

The application runs with default settings. For advanced configuration, modify the `docker-compose.yml` environment variables.

## 📞 Support

For issues and questions, please check the GitHub releases page for updates and documentation.
