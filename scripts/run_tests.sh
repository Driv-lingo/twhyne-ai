#!/bin/bash
# Run all tests for the SNF-AI system
# Usage: ./scripts/run_tests.sh [unit|integration|all]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$ROOT_DIR/backend"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Default admin secret for testing
export SNF_ADMIN_SECRET="${SNF_ADMIN_SECRET:-test-admin-secret}"
export TEST_SERVER_URL="${TEST_SERVER_URL:-http://localhost:5002}"
export LICENSE_SERVER_URL="${LICENSE_SERVER_URL:-http://localhost:5003}"

MODE="${1:-all}"

echo "============================================================"
echo "  SNF-AI Test Runner"
echo "============================================================"

run_unit_tests() {
    echo -e "\n${YELLOW}▸ Running unit tests...${NC}"
    cd "$BACKEND_DIR"
    python3 -m unittest discover -s tests -p 'test_telemetry_admin.py' -v
    echo -e "${GREEN}✓ Unit tests passed${NC}"
}

run_syntax_checks() {
    echo -e "\n${YELLOW}▸ Running syntax checks...${NC}"
    cd "$BACKEND_DIR"
    for f in server.py test_server.py license_api_server.py telemetry.py admin_api.py update_manager.py; do
        python3 -m py_compile "$f" && echo "  ✓ $f"
    done
    echo -e "${GREEN}✓ Syntax checks passed${NC}"
}

start_servers() {
    echo -e "\n${YELLOW}▸ Starting servers for integration tests...${NC}"
    cd "$BACKEND_DIR"
    
    # Start test server
    python3 test_server.py > /tmp/snf_test_server.log 2>&1 &
    TEST_PID=$!
    echo "  Test server PID: $TEST_PID"
    
    # Start license server
    python3 license_api_server.py > /tmp/snf_license_server.log 2>&1 &
    LICENSE_PID=$!
    echo "  License server PID: $LICENSE_PID"
    
    sleep 3
    
    # Verify they started
    if ! kill -0 $TEST_PID 2>/dev/null; then
        echo -e "${RED}✗ Test server failed to start${NC}"
        cat /tmp/snf_test_server.log
        return 1
    fi
    if ! kill -0 $LICENSE_PID 2>/dev/null; then
        echo -e "${RED}✗ License server failed to start${NC}"
        cat /tmp/snf_license_server.log
        return 1
    fi
    
    echo -e "${GREEN}✓ Both servers running${NC}"
}

stop_servers() {
    echo -e "\n${YELLOW}▸ Stopping servers...${NC}"
    kill $(pgrep -f "python3 test_server.py" 2>/dev/null) 2>/dev/null || true
    kill $(pgrep -f "python3 license_api_server.py" 2>/dev/null) 2>/dev/null || true
    echo -e "${GREEN}✓ Servers stopped${NC}"
}

run_integration_tests() {
    echo -e "\n${YELLOW}▸ Running integration tests...${NC}"
    cd "$BACKEND_DIR"
    python3 -m unittest tests.test_integration -v
    echo -e "${GREEN}✓ Integration tests passed${NC}"
}

# Trap to ensure cleanup on exit
cleanup() {
    if [ "$MODE" = "integration" ] || [ "$MODE" = "all" ]; then
        stop_servers
    fi
}
trap cleanup EXIT

case "$MODE" in
    unit)
        run_syntax_checks
        run_unit_tests
        ;;
    integration)
        start_servers
        run_integration_tests
        ;;
    all)
        run_syntax_checks
        run_unit_tests
        start_servers
        run_integration_tests
        ;;
    *)
        echo "Usage: $0 [unit|integration|all]"
        exit 1
        ;;
esac

echo -e "\n${GREEN}============================================================${NC}"
echo -e "${GREEN}  All tests passed! ✓${NC}"
echo -e "${GREEN}============================================================${NC}"
