#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
    
    # Kill any remaining node/python processes from this session
    pkill -P $$ 2>/dev/null
    
    echo -e "${GREEN}✅ Services stopped${NC}"
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM
trap cleanup SIGINT SIGTERM

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

# Ensure model files are downloaded
echo -e "${BLUE}📦 Downloading model files...${NC}"
echo "Starting SNF-AI Windsurf..."

# Check license FIRST
echo "Validating license..."
python3 backend/simple_license_check.py

# If license check passes, continue startup
echo "License valid - proceeding with startup"

# Download models if needed
python3 scripts/download_models_if_needed.py

# Start backend
echo "Starting backend server..."
python3 backend/server.py &

# Start frontend (if built)
if [ -d "frontend/build" ]; then
    echo "Starting frontend..."
    cd frontend
    npx serve -s build -l 3000 &
    cd ..
    exit 1
fi

echo -e "${GREEN}✅ Backend running (PID: $BACKEND_PID)${NC}"
echo ""

# Start Frontend Server
echo -e "${BLUE}🎨 Starting Frontend Server (Port 3001)...${NC}"
cd frontend
PORT=3001 npm start > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait a moment for frontend to initialize
sleep 3

# Check if frontend started successfully
if ! ps -p $FRONTEND_PID > /dev/null; then
    echo -e "${RED}❌ Frontend failed to start. Check logs/frontend.log${NC}"
    cleanup
    exit 1
fi

echo -e "${GREEN}✅ Frontend running (PID: $FRONTEND_PID)${NC}"
echo ""

# Display access information
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ System is running!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}📱 Access Points:${NC}"
echo -e "   Frontend:  ${GREEN}http://localhost:3001${NC}"
echo -e "   Backend:   ${GREEN}http://localhost:5002${NC}"
echo -e "   Status:    ${GREEN}http://localhost:5002/status${NC}"
echo ""
echo -e "${BLUE}📊 Logs:${NC}"
echo -e "   Backend:   ${YELLOW}logs/backend.log${NC}"
echo -e "   Frontend:  ${YELLOW}logs/frontend.log${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
