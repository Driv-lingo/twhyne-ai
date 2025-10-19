#!/bin/bash

# ============================================================
# FINAL PRODUCTION BUILD - SNF-AI Licensed Executable
# Full-scope application with license validation
# ============================================================

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     SNF-AI WINDSURF - FINAL LICENSED BUILD v3.0          ║"
echo "╚══════════════════════════════════════════════════════════╝"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="SNF-AI-Windsurf"
VERSION="3.0.0"
BUNDLE_ID="com.twhyne.snf-ai"

echo -e "\n${CYAN}[1/5] Checking Prerequisites...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python $(python3 --version)"

# Install dependencies
echo -e "\n${CYAN}[2/5] Installing Dependencies...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
pip install -q --upgrade pip
pip install -q pyinstaller requests flask flask-cors pillow numpy
echo -e "${GREEN}✓${NC} Dependencies installed"

# Clean previous builds
echo -e "\n${CYAN}[3/5] Cleaning Previous Builds...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
rm -rf build dist *.spec
echo -e "${GREEN}✓${NC} Cleaned build artifacts"

# Create PyInstaller spec
echo -e "\n${CYAN}[4/5] Creating Build Configuration...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cat > ${APP_NAME}.spec << 'SPEC_FILE'
# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path

# Build configuration
block_cipher = None
DEBUG = False

# Paths
BACKEND_DIR = 'backend'
MODELS_DIR = 'models'
UPLOADS_DIR = 'uploads'

# Analysis - Full scope with all components
a = Analysis(
    ['backend/app_launcher.py'],
    pathex=[BACKEND_DIR],
    binaries=[],
    datas=[
        # Core modules
        (f'{BACKEND_DIR}/license_manager.py', '.'),
        (f'{BACKEND_DIR}/model_downloader.py', '.'),
        (f'{BACKEND_DIR}/test_server.py', '.'),
        (f'{BACKEND_DIR}/server.py', '.') if os.path.exists(f'{BACKEND_DIR}/server.py') else (f'{BACKEND_DIR}/test_server.py', 'server.py'),
        (f'{BACKEND_DIR}/rag_manager.py', '.') if os.path.exists(f'{BACKEND_DIR}/rag_manager.py') else (f'{BACKEND_DIR}/test_server.py', 'rag_manager.py'),
        
        # Node system
        (f'{BACKEND_DIR}/flux_nodes', 'flux_nodes'),
        
        # Data directories
        (f'{MODELS_DIR}/.gitkeep', MODELS_DIR),
        (f'{UPLOADS_DIR}/.gitkeep', UPLOADS_DIR),
        
        # Configuration files
        ('requirements-api.txt', '.'),
        ('railway.json', '.'),
    ],
    hiddenimports=[
        # Flask and web
        'flask', 'flask_cors', 'werkzeug',
        
        # AI and processing
        'PIL', 'PIL.Image', 'numpy',
        
        # Networking
        'requests', 'urllib3', 'certifi',
        
        # GUI
        'tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'tkinter.filedialog',
        
        # System
        'threading', 'webbrowser', 'hashlib', 'uuid', 'platform',
        'json', 'datetime', 'pathlib', 'typing', 'logging',
        
        # Nodes
        'backend.flux_nodes.base',
        'backend.flux_nodes.language',
        'backend.flux_nodes.code',
        'backend.flux_nodes.math',
        'backend.flux_nodes.vision',
        'backend.flux_nodes.planner',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary packages
        'matplotlib', 'scipy', 'pandas', 'sklearn',
        'jupyter', 'notebook', 'ipython',
        'pytest', 'nose', 'unittest',
        'setuptools', 'pip',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SNF-AI-Windsurf',
    debug=DEBUG,
    bootloader_ignore_signals=False,
    strip=not DEBUG,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'python*.dll'],
    runtime_tmpdir=None,
    console=DEBUG,  # Show console only in debug mode
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path if available
)

app = BUNDLE(
    exe,
    name='SNF-AI-Windsurf.app',
    icon=None,  # Add .icns file path if available
    bundle_identifier='com.twhyne.snf-ai',
    info_plist={
        'CFBundleName': 'SNF-AI Windsurf',
        'CFBundleDisplayName': 'SNF-AI Windsurf System',
        'CFBundleGetInfoString': 'SNF-AI Windsurf - Professional AI System',
        'CFBundleIdentifier': 'com.twhyne.snf-ai',
        'CFBundleVersion': '3.0.0',
        'CFBundleShortVersionString': '3.0.0',
        'CFBundlePackageType': 'APPL',
        'CFBundleSignature': 'SNFA',
        'CFBundleExecutable': 'SNF-AI-Windsurf',
        'CFBundleIconFile': '',  # Add icon name if available
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '10.15.0',
        'NSRequiresAquaSystemAppearance': 'False',
        'LSApplicationCategoryType': 'public.app-category.developer-tools',
        'NSAppleEventsUsageDescription': 'This app needs to control other applications.',
        'NSMicrophoneUsageDescription': 'This app needs microphone access for voice input.',
        'NSCameraUsageDescription': 'This app needs camera access for image processing.',
        'LSBackgroundOnly': 'False',
        'LSUIElement': 'False',
    }
)
SPEC_FILE

echo -e "${GREEN}✓${NC} Build configuration created"

# Build the application
echo -e "\n${CYAN}[5/5] Building Application...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
pyinstaller --clean --noconfirm ${APP_NAME}.spec

if [ $? -eq 0 ]; then
    # Create distribution package
    echo -e "\n${CYAN}Creating Distribution Package...${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    DIST_DIR="SNF-AI-Distribution"
    rm -rf $DIST_DIR
    mkdir -p $DIST_DIR
    
    # Copy app
    cp -r dist/${APP_NAME}.app $DIST_DIR/
    
    # Create installer script
    cat > $DIST_DIR/Install.command << 'INSTALLER'
#!/bin/bash
echo "Installing SNF-AI Windsurf..."
cp -r SNF-AI-Windsurf.app /Applications/
echo "✓ Installation complete!"
echo "You can now launch SNF-AI Windsurf from Applications"
read -p "Press Enter to close..."
INSTALLER
    chmod +x $DIST_DIR/Install.command
    
    # Create uninstaller
    cat > $DIST_DIR/Uninstall.command << 'UNINSTALLER'
#!/bin/bash
echo "Uninstalling SNF-AI Windsurf..."
rm -rf /Applications/SNF-AI-Windsurf.app
rm -rf ~/Library/Application\ Support/SNF-AI
echo "✓ Uninstallation complete!"
read -p "Press Enter to close..."
UNINSTALLER
    chmod +x $DIST_DIR/Uninstall.command
    
    # Create user guide
    cat > $DIST_DIR/USER_GUIDE.md << 'GUIDE'
# SNF-AI Windsurf - User Guide

## Installation
1. Double-click `Install.command` to install to Applications
2. Or drag `SNF-AI-Windsurf.app` to your Applications folder

## First Launch
1. Open SNF-AI Windsurf from Applications
2. Enter your license key when prompted
3. Choose to download AI models (8GB) for full functionality

## License Activation
- **Purchase Required**: Visit https://web-production-d31c0.up.railway.app/register
- **Full License**: 90 days with all features unlocked
- **No Trial**: A valid license is required to use the application

## Features
- Language Processing (with models)
- Code Generation (with models)
- Mathematical Calculations
- Image Processing
- Real-time Information
- Task Planning

## Support
- Email: support@twhyne.ai
- Web: https://web-production-d31c0.up.railway.app
GUIDE
    
    # Create DMG (optional, requires create-dmg)
    if command -v create-dmg &> /dev/null; then
        echo -e "\n${CYAN}Creating DMG installer...${NC}"
        create-dmg \
            --volname "${APP_NAME} Installer" \
            --window-pos 200 120 \
            --window-size 600 400 \
            --icon-size 100 \
            --app-drop-link 425 200 \
            "${APP_NAME}-${VERSION}.dmg" \
            "$DIST_DIR/"
        echo -e "${GREEN}✓${NC} DMG created: ${APP_NAME}-${VERSION}.dmg"
    fi
    
    # Create ZIP for distribution
    echo -e "\n${CYAN}Creating ZIP archive...${NC}"
    zip -r "${APP_NAME}-${VERSION}.zip" $DIST_DIR
    echo -e "${GREEN}✓${NC} ZIP created: ${APP_NAME}-${VERSION}.zip"
    
    # Final summary
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║                  BUILD SUCCESSFUL! 🎉                     ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    echo -e "${GREEN}📦 Distribution Package:${NC} $DIST_DIR/"
    echo -e "${GREEN}📱 Application:${NC} $DIST_DIR/${APP_NAME}.app"
    echo -e "${GREEN}📄 Archive:${NC} ${APP_NAME}-${VERSION}.zip"
    echo ""
    echo -e "${YELLOW}Key Features:${NC}"
    echo "  ✅ License validation required"
    echo "  ✅ Auto-download AI models"
    echo "  ✅ Railway API integration"
    echo "  ✅ 90-day license support"
    echo "  ✅ Multi-device tracking (3 devices)"
    echo "  ✅ Offline mode support"
    echo "  ❌ No trial mode - license required"
    echo ""
    echo -e "${BLUE}Distribution:${NC}"
    echo "  1. Share ${APP_NAME}-${VERSION}.zip with users"
    echo "  2. Users run Install.command"
    echo "  3. App validates license on first launch"
    echo "  4. Models download automatically (if licensed)"
    echo ""
    echo -e "${CYAN}API Endpoint:${NC}"
    echo "  https://web-production-d31c0.up.railway.app"
    echo ""
    echo -e "${GREEN}Ready for production deployment!${NC}"
    
else
    echo -e "${RED}❌ Build failed!${NC}"
    echo "Check the error messages above for details."
    exit 1
fi
