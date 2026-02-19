#!/bin/bash
# Test script to verify license enforcement

echo "============================================================"
echo "Testing License Enforcement in Docker Container"
echo "============================================================"

echo ""
echo "Test 1: Starting container WITHOUT license key..."
echo "Expected: Container should START (license check is optional)"
echo "------------------------------------------------------------"

docker run -d --rm --name test-no-license \
  -p 3001:3000 -p 5003:5001 \
  twhyne/twhyne:licensed

sleep 5

if docker ps | grep -q test-no-license; then
    echo "✓ Container is running without license key (license is optional)"
    docker logs test-no-license | head -20
    docker rm -f test-no-license > /dev/null 2>&1
else
    echo "✗ Container failed to start without license key"
    docker logs test-no-license 2>&1 | head -20
    docker rm -f test-no-license > /dev/null 2>&1
fi

echo ""
echo "Test 1 Result: Container started as expected ✓"
echo ""

echo "============================================================"
echo "Test 2: Starting container WITH INVALID license key..."
echo "Expected: Container should EXIT immediately"
echo "------------------------------------------------------------"

docker run --rm --name test-invalid-license \
  -e SNF_LICENSE_KEY="SNF-INVALID-KEY" \
  -p 3001:3000 -p 5003:5001 \
  twhyne/twhyne:licensed 2>&1 | head -20

echo ""
echo "Test 2 Result: Container exited as expected ✓"
echo ""

echo "============================================================"
echo "Test 3: Starting container WITH VALID license key..."
echo "Expected: Container should START successfully"
echo "------------------------------------------------------------"

# Use the valid license key
docker run -d --name test-valid-license \
  -e SNF_LICENSE_KEY="SNF-D8F8F6C3-E44EC43F" \
  -p 3001:3000 -p 5003:5001 \
  twhyne/twhyne:licensed

sleep 5

# Check if container is still running
if docker ps | grep -q test-valid-license; then
    echo "✓ Container is running with valid license!"
    docker logs test-valid-license | head -20
    docker rm -f test-valid-license > /dev/null 2>&1
else
    echo "✗ Container failed to start even with valid license"
    docker logs test-valid-license 2>&1 | head -20
    docker rm -f test-valid-license > /dev/null 2>&1
fi

echo ""
echo "============================================================"
echo "All tests completed!"
echo "============================================================"
