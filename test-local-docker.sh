#!/bin/bash

echo "🧪 Testing Local Docker Build..."

# Stop any existing containers
docker stop snf-test 2>/dev/null || true
docker rm snf-test 2>/dev/null || true

# Run the locally built image
echo "Starting container..."
docker run -d --name snf-test \
  -p 3000:3000 \
  -p 5001:5001 \
  twhyne/twhyne:prod-local

echo ""
echo "Waiting for services to start..."
sleep 10

# Test backend
echo ""
echo "Testing backend (port 5001)..."
curl -s http://localhost:5001/status | jq . || echo "❌ Backend not responding"

# Test frontend
echo ""
echo "Testing frontend (port 3000)..."
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost:3000

echo ""
echo "View logs with: docker logs -f snf-test"
echo "Stop with: docker stop snf-test && docker rm snf-test"
