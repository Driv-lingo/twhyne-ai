#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect if running inside Docker
if [ -f "/.dockerenv" ] || [ -n "$container" ] || grep -qsF docker /proc/1/cgroup 2>/dev/null; then
    DOCKER_MODE=true
else
    DOCKER_MODE=false
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🚀 Starting SNF-AI Windsurf System${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}🛑 Shutting down services...${NC}"

    # Kill backend
    if [ ! -z "$BACKEND_PID" ]; then
        echo -e "${YELLOW}Stopping backend (PID: $BACKEND_PID)...${NC}"
        kill $BACKEND_PID 2>/dev/null
    fi

    # Kill frontend
    if [ ! -z "$FRONTEND_PID" ]; then
        echo -e "${YELLOW}Stopping frontend (PID: $FRONTEND_PID)...${NC}"
        kill $FRONTEND_PID 2>/dev/null
    fi

    echo -e "${GREEN}✅ Services stopped${NC}"
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM
trap cleanup SIGINT SIGTERM

# --- Local-only: check prerequisites and install dependencies ---
if [ "$DOCKER_MODE" = false ]; then
    # Check if Python is installed
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is required but not installed.${NC}"
        exit 1
    fi

    # Check if Node.js is installed
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js is required but not installed.${NC}"
        exit 1
    fi

    # Check if dependencies are installed
    echo -e "${BLUE}📦 Checking dependencies...${NC}"

    if [ ! -d "frontend/node_modules" ]; then
        echo -e "${YELLOW}Installing frontend dependencies...${NC}"
        cd frontend
        npm install
        cd ..
    fi

    if ! python3 -c "import flask" 2>/dev/null; then
        echo -e "${YELLOW}Installing Python dependencies...${NC}"
        pip3 install -r requirements.txt
    fi

    echo -e "${GREEN}✅ Dependencies ready${NC}"
    echo ""
fi

# Check license (optional - skipped if SNF_LICENSE_KEY is not set)
echo -e "${BLUE}🔑 Validating license...${NC}"
if [ -n "$SNF_LICENSE_KEY" ]; then
    python3 backend/simple_license_check.py
    echo -e "${GREEN}✅ License valid - proceeding with startup${NC}"
else
    echo "No license key provided - skipping license validation"
    echo "Set SNF_LICENSE_KEY to enable license enforcement"
fi
echo ""

# Download models if needed (non-blocking)
if [ -f "scripts/download_models.py" ]; then
    echo -e "${BLUE}📦 Checking model files...${NC}"
    python3 scripts/download_models.py || echo "Model download skipped or failed, continuing..."
fi

# Start backend
echo -e "${BLUE}🔧 Starting backend server...${NC}"
cd "$SCRIPT_DIR/backend"
python3 server.py &
BACKEND_PID=$!
cd "$SCRIPT_DIR"
echo -e "${GREEN}✅ Backend running (PID: $BACKEND_PID)${NC}"
echo ""

# --- Local-only: start a frontend dev server ---
if [ "$DOCKER_MODE" = false ]; then
    if [ -d "frontend/node_modules" ]; then
        echo -e "${BLUE}🎨 Starting Frontend Server (Port 3001)...${NC}"
        cd frontend
        PORT=3001 npm start > ../logs/frontend.log 2>&1 &
        FRONTEND_PID=$!
        cd ..

        sleep 3

        if ps -p $FRONTEND_PID > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Frontend running (PID: $FRONTEND_PID)${NC}"
        else
            echo -e "${RED}❌ Frontend failed to start. Check logs/frontend.log${NC}"
            cleanup
            exit 1
        fi
        echo ""
    fi
fi

# Display access information
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ System is running!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}📱 Access Points:${NC}"
if [ "$DOCKER_MODE" = true ]; then
    echo -e "   Application: ${GREEN}http://localhost:${PORT:-5002}${NC}"
    echo -e "   Backend API: ${GREEN}http://localhost:${PORT:-5002}/status${NC}"
else
    echo -e "   Frontend:  ${GREEN}http://localhost:3001${NC}"
    echo -e "   Backend:   ${GREEN}http://localhost:5002${NC}"
    echo -e "   Status:    ${GREEN}http://localhost:5002/status${NC}"
    echo ""
    echo -e "${BLUE}📊 Logs:${NC}"
    echo -e "   Backend:   ${YELLOW}logs/backend.log${NC}"
    echo -e "   Frontend:  ${YELLOW}logs/frontend.log${NC}"
fi
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for processes
if [ ! -z "$FRONTEND_PID" ]; then
    wait $BACKEND_PID $FRONTEND_PID
else
    wait $BACKEND_PID
fi
