#!/bin/bash

# Script to deploy the executable to Railway for user downloads

echo "═══════════════════════════════════════════════════════"
echo "   SNF-AI Executable Deployment to Railway"
echo "═══════════════════════════════════════════════════════"

# Configuration
RAILWAY_URL="https://web-production-d31c0.up.railway.app"
APP_FILE="SNF-AI-Windsurf-3.0.0.zip"
ADMIN_TOKEN=${ADMIN_TOKEN:-"your-secret-admin-token"}

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if executable exists
if [ ! -f "$APP_FILE" ]; then
    echo -e "${RED}Error: $APP_FILE not found!${NC}"
    echo "Please build the application first using BUILD_FINAL.sh"
    exit 1
fi

echo -e "${YELLOW}Uploading $APP_FILE to Railway...${NC}"

# Upload the file
response=$(curl -X POST \
    -H "X-Admin-Token: $ADMIN_TOKEN" \
    -F "file=@$APP_FILE" \
    "$RAILWAY_URL/upload")

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Upload successful!${NC}"
    echo "Response: $response"
    echo ""
    echo -e "${GREEN}Users can now download the app after registration at:${NC}"
    echo "$RAILWAY_URL/download/{license_key}"
else
    echo -e "${RED}❌ Upload failed!${NC}"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo -e "${GREEN}Deployment Complete!${NC}"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Registration Flow:"
echo "1. User registers at: $RAILWAY_URL/register"
echo "2. Receives license key via email"
echo "3. Redirected to: $RAILWAY_URL/download/{license_key}"
echo "4. Downloads the application"
echo "5. Installs and activates with license key"
