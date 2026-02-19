# SNF-AI Windsurf - Clean Implementation

A streamlined, production-ready implementation of the SNF-AI Windsurf modular AI mesh routing system.

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+
- 8GB+ RAM
- 4GB+ free disk space

### Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Node.js dependencies:**
   ```bash
   cd frontend
   npm install
   ```

3. **Start the backend server:**
   ```bash
   ./scripts/start_backend.sh
   ```

4. **Start the frontend (in a new terminal):**
   ```bash
   ./scripts/start_frontend.sh
   ```

5. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:5002

## 🏗️ Architecture

### Backend (`/backend`)
- **Flask API Server** (`server.py`) - Main API server with routing logic
- **Expert Nodes** (`/flux_nodes/`) - Specialized AI nodes:
  - `language.py` - General language processing (Mistral-7B)
  - `code.py` - Code generation (CodeLlama-7B) 
  - `math.py` - Mathematical problem solving (Mistral-7B)
  - `planner.py` - Task planning (Mistral-7B)
  - `vision.py` - Image analysis (LLaVA-1.6-7B)
- **Base Classes** (`base.py`) - Core node infrastructure

### Frontend (`/frontend`)
- **React Application** - Modern web interface
- **Node Visualization** - Real-time node status display
- **Chat Interface** - Interactive query system
- **RAG Management** - Document upload and management

### Models (`/models`)
- **Mistral-7B-Instruct** (4.1GB) - Language, Math, Planning
- **CodeLlama-7B** (4.0GB) - Code generation
- **LLaVA-1.6-7B** (4.0GB) - Vision processing
- **MMProj** (600MB) - Vision projection model

## 🔧 API Endpoints

- `GET /status` - System health check
- `GET /nodes` - List all available nodes
- `POST /query` - Submit queries for processing

## 📊 Features

- **Modular Architecture** - Specialized nodes for different tasks
- **Intelligent Routing** - Automatic query routing based on content
- **Real-time Processing** - Live node status and response streaming
- **Offline Capability** - Full functionality without internet
- **Fallback Mechanisms** - Graceful handling of node failures

## 🛠️ Development

### Adding New Nodes

1. Create a new node class inheriting from `FluxNode`
2. Implement the `generate()` method
3. Register the node in `server.py`
4. Add routing logic in `_route_query()`

### Customizing Routing

Modify the `_route_query()` function in `server.py` to add new routing patterns:

```python
# Add new routing logic
if "your_keyword" in prompt_lower:
    node = node_registry.get_node('your-node-id')
    if node and node.is_available:
        return node
```

## Quick Start with Docker

Get SNF-AI Windsurf running in minutes with our pre-built Docker image!

### Prerequisites
- Docker and Docker Compose installed on your system
- At least 8GB of available disk space (for model files)

### One-Command Setup
```bash
# Download and run the latest version
curl -O https://twhyne.com/docker-compose.yml
docker-compose up -d
```

### Manual Setup
1. **Pull the Docker Image**:
   ```bash
   docker pull TWHYNE/twhyne:latest
   ```

2. **Run with Docker Compose** (Recommended):
   ```bash
   # Download the docker-compose file
   curl -O https://twhyne.com/docker-compose.yml
   
   # Start the application
   docker-compose up -d
   ```

3. **Or Run Directly**:
   ```bash
   docker run -d \
     --name snf-ai-windsurf \
     -p 3000:3000 \
     -p 5002:5002 \
     -v snf_models:/app/models \
     -v snf_logs:/app/logs \
     TWHYNE/twhyne:latest
   ```

### Access Your Application
- **Frontend**: Open `http://localhost:3000` in your browser
- **Backend API**: Available at `http://localhost:5002`

### Important Notes
- **First Run**: Model download takes 10-15 minutes (downloads ~8GB of AI models)
- **Persistence**: Models and logs are saved in Docker volumes for faster restarts
- **Stop**: Use `docker-compose down` to stop



## 📝 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📞 Support

For issues and questions, please open an issue on GitHub.
# Updated Sun Oct 26 14:58:17 EDT 2025
