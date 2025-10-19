#!/bin/bash

# Build script for SNF-AI macOS executable with automatic model downloading
# This creates a smart executable that downloads models on first run

echo "🔨 Building SNF-AI Smart Executable with Auto-Download..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check dependencies
echo -e "${BLUE}Checking dependencies...${NC}"

# Install required packages
pip install pyinstaller requests tkinter pillow numpy flask flask-cors

# Create the PyInstaller spec file
cat > snf_ai_smart.spec << 'EOF'
# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

# Analysis for the smart SNF-AI system with auto-download
a = Analysis(
    ['backend/app_launcher.py'],
    pathex=['backend'],
    binaries=[],
    datas=[
        ('backend/model_downloader.py', '.'),
        ('backend/test_server.py', '.'),
        ('backend/flux_nodes', 'flux_nodes'),
        ('models/.gitkeep', 'models'),
        ('uploads/.gitkeep', 'uploads'),
    ],
    hiddenimports=[
        'flask',
        'flask_cors',
        'PIL',
        'PIL.Image',
        'numpy',
        'requests',
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'threading',
        'webbrowser',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'pandas',
        'jupyter',
        'notebook',
        'ipython',
        'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SNF-AI-Windsurf',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='SNF-AI-Windsurf.app',
    icon=None,
    bundle_identifier='com.twhyne.snf-ai',
    info_plist={
        'CFBundleName': 'SNF-AI Windsurf',
        'CFBundleDisplayName': 'SNF-AI Windsurf System',
        'CFBundleGetInfoString': "SNF-AI Windsurf - Intelligent Multi-Node AI System",
        'CFBundleIdentifier': 'com.twhyne.snf-ai',
        'CFBundleVersion': '2.0.0',
        'CFBundleShortVersionString': '2.0.0',
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '10.15.0',
        'NSRequiresAquaSystemAppearance': 'False',
        'LSApplicationCategoryType': 'public.app-category.developer-tools',
    }
)
EOF

echo -e "${GREEN}✅ Created smart PyInstaller spec file${NC}"

# Build the executable
echo -e "${BLUE}Building executable...${NC}"
pyinstaller --clean --noconfirm snf_ai_smart.spec

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Build successful!${NC}"
    
    # Create a nice README for the app
    cat > dist/README.md << 'EOF'
# SNF-AI Windsurf System

## Quick Start

1. **Double-click** `SNF-AI-Windsurf.app` to launch
2. **First Run**: The app will offer to download AI models (~8GB)
   - Choose "Download" for full functionality
   - Choose "Skip" for limited mode (Math, Vision, Real-time only)
3. **Access**: Open http://localhost:5002 in your browser

## Features

### With Models (Full Mode)
- ✅ Language Processing
- ✅ Code Generation
- ✅ Mathematical Calculations
- ✅ Image Processing
- ✅ Real-time Information
- ✅ Task Planning

### Without Models (Limited Mode)
- ✅ Mathematical Calculations
- ✅ Image Processing
- ✅ Real-time Information
- ❌ Language Processing
- ❌ Code Generation

## Model Download

The app will automatically download models on first run:
- **Mistral 7B** (4.37 GB) - Language understanding
- **CodeLlama 7B** (4.08 GB) - Code generation

Download time depends on your internet speed (typically 10-30 minutes).

## API Endpoints

- `GET http://localhost:5002/status` - Health check
- `GET http://localhost:5002/nodes` - Available nodes
- `POST http://localhost:5002/query` - Send queries
- `POST http://localhost:5002/upload` - Upload images

## Troubleshooting

### App won't open
```bash
xattr -cr SNF-AI-Windsurf.app
```

### Port already in use
```bash
lsof -ti:5002 | xargs kill -9
```

### Re-download models
Delete the `models` folder inside the app and restart.

## Support

- GitHub: https://github.com/Driv-lingo/twhyne-ai
- API Docs: http://localhost:5002/docs (when running)

---
Version 2.0.0 - With Smart Model Downloading
EOF
    
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✅ Smart Executable Build Complete!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BLUE}📦 Location:${NC} dist/SNF-AI-Windsurf.app"
    echo ""
    echo -e "${YELLOW}✨ Features:${NC}"
    echo "   • Automatic model download on first run"
    echo "   • GUI interface for download progress"
    echo "   • Works immediately (limited mode)"
    echo "   • Full mode after model download"
    echo "   • Small initial size (~50MB)"
    echo ""
    echo -e "${BLUE}📱 To Install:${NC}"
    echo "   cp -r dist/SNF-AI-Windsurf.app /Applications/"
    echo ""
    echo -e "${BLUE}🚀 To Run:${NC}"
    echo "   open dist/SNF-AI-Windsurf.app"
    echo ""
    echo -e "${GREEN}The app will guide users through model download on first run!${NC}"
    
else
    echo -e "${RED}❌ Build failed!${NC}"
    echo "Check the error messages above for details."
    exit 1
fi
