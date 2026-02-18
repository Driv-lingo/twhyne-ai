#!/bin/bash
# Run the SNF-AI system locally in demo mode
# No AI models required - uses mock responses to demonstrate the UI
#
# Usage: ./scripts/run_local.sh
# The frontend will be available at http://localhost:3001
# The backend API will be available at http://localhost:5002

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

BACKEND_PID=""
FRONTEND_PID=""
FRONTEND_STARTUP_TIMEOUT=60

cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    if [ -n "$BACKEND_PID" ]; then kill $BACKEND_PID 2>/dev/null || true; fi
    if [ -n "$FRONTEND_PID" ]; then kill $FRONTEND_PID 2>/dev/null || true; fi
    echo -e "${GREEN}Stopped.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  SNF-AI Windsurf - Local Demo${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}▸ Checking prerequisites...${NC}"
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}Python 3 is required${NC}"; exit 1; }
command -v node >/dev/null 2>&1 || { echo -e "${RED}Node.js is required${NC}"; exit 1; }

# Install backend deps if needed
python3 -c "import flask" 2>/dev/null || {
    echo -e "${YELLOW}  Installing Python dependencies...${NC}"
    pip3 install flask flask-cors requests
}

# Install frontend deps if needed
if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
    echo -e "${YELLOW}  Installing frontend dependencies...${NC}"
    cd "$ROOT_DIR/frontend"
    npm install --legacy-peer-deps
    cd "$ROOT_DIR"
fi
echo -e "${GREEN}✓ Prerequisites ready${NC}"

# Start backend (demo mode)
echo -e "\n${YELLOW}▸ Starting backend API server (port 5002)...${NC}"
cd "$ROOT_DIR/backend"
python3 test_server.py > /tmp/snf_backend.log 2>&1 &
BACKEND_PID=$!
sleep 2

if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}✗ Backend failed to start. Logs:${NC}"
    cat /tmp/snf_backend.log
    exit 1
fi

# Verify backend health
if curl -s http://localhost:5002/status | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])" 2>/dev/null | grep -q healthy; then
    echo -e "${GREEN}✓ Backend running at http://localhost:5002${NC}"
else
    echo -e "${RED}✗ Backend health check failed${NC}"
    cat /tmp/snf_backend.log
    exit 1
fi

# Start frontend
echo -e "\n${YELLOW}▸ Starting frontend (port 3001)...${NC}"
cd "$ROOT_DIR/frontend"
PORT=3001 BROWSER=none npm start > /tmp/snf_frontend.log 2>&1 &
FRONTEND_PID=$!

# Wait for frontend to be ready
echo -e "  Waiting for frontend to compile..."
for i in $(seq 1 $FRONTEND_STARTUP_TIMEOUT); do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:3001 2>/dev/null | grep -q "200"; then
        break
    fi
    sleep 2
done

if curl -s -o /dev/null -w "%{http_code}" http://localhost:3001 2>/dev/null | grep -q "200"; then
    echo -e "${GREEN}✓ Frontend running at http://localhost:3001${NC}"
else
    echo -e "${YELLOW}⚠ Frontend may still be compiling - check http://localhost:3001 in a moment${NC}"
fi

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  System is running!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "  ${BLUE}Frontend:${NC}  http://localhost:3001"
echo -e "  ${BLUE}Backend:${NC}   http://localhost:5002"
echo -e "  ${BLUE}Status:${NC}    http://localhost:5002/status"
echo -e "  ${BLUE}Nodes:${NC}     http://localhost:5002/nodes"
echo ""
echo -e "  ${YELLOW}Note: Running in demo mode (mock AI responses)${NC}"
echo -e "  ${YELLOW}For real AI, download models and run: python3 backend/server.py${NC}"
echo ""
echo -e "  Press Ctrl+C to stop"
echo ""

# Wait for either process to exit
wait $BACKEND_PID $FRONTEND_PID
