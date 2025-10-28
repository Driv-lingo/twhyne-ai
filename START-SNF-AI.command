#!/bin/bash
# SNF-AI Starter - Just double-click this file!
# For Mac users - saves as .command to be double-clickable

clear
echo "╔══════════════════════════════════════════╗"
echo "║        SNF-AI WINDSURF STARTER          ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo ""
    echo "Please start Docker Desktop first, then run this again."
    echo ""
    echo "Press Enter to exit..."
    read
    exit 1
fi

# Check for license file
LICENSE_FILE="$HOME/.snf-ai-license"
if [ -f "$LICENSE_FILE" ]; then
    LICENSE_KEY=$(cat "$LICENSE_FILE")
    echo "✓ License found: ${LICENSE_KEY:0:12}..."
else
    echo "📝 First time setup - Enter your license key"
    echo ""
    echo "Get your license at:"
    echo "https://sunny-imagination-production.up.railway.app"
    echo ""
    read -p "License key (SNF-XXXXXXXX-XXXXXXXX): " LICENSE_KEY
    
    if [ -z "$LICENSE_KEY" ]; then
        echo "❌ No license key entered"
        echo "Press Enter to exit..."
        read
        exit 1
    fi
    
    # Save for next time
    echo "$LICENSE_KEY" > "$LICENSE_FILE"
    echo "✓ License saved for future use"
fi

echo ""
echo "🚀 Starting SNF-AI..."
echo ""

# Stop old container if running
docker stop twhyne 2>/dev/null && echo "Stopped old instance"
docker rm twhyne 2>/dev/null

# Pull latest (will use cached if offline)
echo "Checking for updates..."
docker pull twhyne/twhyne:licensed 2>/dev/null || echo "Using cached version (offline mode)"

# Start container
echo "Starting application..."
docker run -d \
  --name twhyne \
  -e SNF_LICENSE_KEY="$LICENSE_KEY" \
  -p 3000:3000 \
  -p 5001:5001 \
  --mount source=snf_models,target=/app/models \
  --mount source=snf_logs,target=/app/logs \
  --mount source=snf_data,target=/app/data \
  --mount source=snf_uploads,target=/app/uploads \
  --mount source=snf_rag,target=/app/rag_storage \
  --mount source=snf_conversations,target=/app/conversations \
  --restart unless-stopped \
  twhyne/twhyne:licensed > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SNF-AI is running!"
    echo ""
    echo "Opening in browser..."
    sleep 3
    open http://localhost:3000
    
    # Clean up old images to save space
    echo "Cleaning up old versions..."
    docker image prune -f > /dev/null 2>&1
    
    echo ""
    echo "════════════════════════════════════════"
    echo "  Access at: http://localhost:3000"
    echo "  To stop: Run STOP-SNF-AI"
    echo "════════════════════════════════════════"
else
    echo ""
    echo "❌ Failed to start"
    echo "Check that Docker is running and try again"
fi

echo ""
echo "Press Enter to close this window..."
read
