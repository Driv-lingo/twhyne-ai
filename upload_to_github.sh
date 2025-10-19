#!/bin/bash

# Upload executable to GitHub Releases

echo "═══════════════════════════════════════════════════════"
echo "   Upload SNF-AI to GitHub Releases"
echo "═══════════════════════════════════════════════════════"

# Configuration
REPO="Driv-lingo/twhyne-ai"
VERSION="v3.0.0"
RELEASE_NAME="SNF-AI Windsurf v3.0.0 - Licensed Edition"
FILE="SNF-AI-Windsurf-3.0.0.zip"

# Check if file exists
if [ ! -f "$FILE" ]; then
    echo "Error: $FILE not found!"
    exit 1
fi

# Create release notes
cat > release_notes.md << 'EOF'
# SNF-AI Windsurf v3.0.0 - Licensed Edition

## 🔐 License Required
This version requires a valid license key to operate. No trial mode available.

## Features
- ✅ Full AI node system (6 nodes)
- ✅ Automatic model downloading (~8GB)
- ✅ License validation with Railway API
- ✅ 90-day license duration
- ✅ Multi-device support (3 devices)
- ✅ Offline mode capability

## Installation
1. Purchase license at: https://web-production-d31c0.up.railway.app/register
2. Download SNF-AI-Windsurf-3.0.0.zip
3. Extract and run `Install.command`
4. Enter your license key when prompted
5. App will download AI models on first run

## System Requirements
- macOS 10.15 or later
- 8GB RAM minimum (16GB recommended)
- 10GB free disk space
- Internet connection for activation

## Support
- Email: support@twhyne.ai
- License Portal: https://web-production-d31c0.up.railway.app
EOF

echo "Creating GitHub Release..."

# Create release using GitHub CLI (if installed)
if command -v gh &> /dev/null; then
    gh release create $VERSION \
        --repo $REPO \
        --title "$RELEASE_NAME" \
        --notes-file release_notes.md \
        $FILE
    
    echo "✅ Release created successfully!"
    echo "Download URL: https://github.com/$REPO/releases/latest"
else
    echo "GitHub CLI not found. Please install it with:"
    echo "  brew install gh"
    echo ""
    echo "Or manually create a release at:"
    echo "  https://github.com/$REPO/releases/new"
    echo ""
    echo "Upload file: $FILE"
fi

rm release_notes.md
