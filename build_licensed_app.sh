#!/bin/bash

# Build script for SNF-AI macOS executable with License System
# This creates a complete executable with license validation and auto-download

echo "🔨 Building SNF-AI Licensed Executable..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
pip install pyinstaller requests tkinter pillow numpy flask flask-cors

# Create the PyInstaller spec file with license system
cat > snf_ai_licensed.spec << 'EOF'
# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

# Analysis for the licensed SNF-AI system
a = Analysis(
    ['backend/app_launcher.py'],
    pathex=['backend'],
    binaries=[],
    datas=[
        ('backend/model_downloader.py', '.'),
        ('backend/license_manager.py', '.'),
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
        'hashlib',
        'uuid',
        'platform',
        'json',
        'datetime',
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
        'CFBundleGetInfoString': "SNF-AI Windsurf - Licensed AI System",
        'CFBundleIdentifier': 'com.twhyne.snf-ai',
        'CFBundleVersion': '3.0.0',
        'CFBundleShortVersionString': '3.0.0',
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '10.15.0',
        'NSRequiresAquaSystemAppearance': 'False',
        'LSApplicationCategoryType': 'public.app-category.developer-tools',
        'NSAppleEventsUsageDescription': 'This app needs to control other applications.',
    }
)
EOF

echo -e "${GREEN}✅ Created licensed app spec file${NC}"

# Build the executable
echo -e "${BLUE}Building licensed executable...${NC}"
pyinstaller --clean --noconfirm snf_ai_licensed.spec

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Build successful!${NC}"
    
    # Create README for the licensed app
    cat > dist/README_LICENSED.md << 'EOF'
# SNF-AI Windsurf System - Licensed Edition

## 🔐 License Activation Required

This application requires a valid license key to operate.

## Quick Start

1. **Launch the App**
   ```bash
   open SNF-AI-Windsurf.app
   ```

2. **License Activation**
   - Enter your license key
   - Or click "Get License" to purchase
   - Or start a 7-day trial

3. **Model Download** (Full License Only)
   - After activation, choose to download AI models
   - ~8GB download for full functionality

## License Options

### Full License (90 Days)
- ✅ All AI nodes enabled
- ✅ Unlimited queries
- ✅ Model downloads included
- ✅ Priority support
- ✅ Multi-device support (3 devices)

### Trial License (7 Days)
- ✅ Math & Vision nodes only
- ⚠️ 100 queries/day limit
- ❌ No model downloads
- ❌ No language/code generation

## Activation Process

1. **Online Activation** (Recommended)
   - Enter license key
   - Validates with server
   - Instant activation

2. **Offline Activation**
   - Works with cached license
   - Limited validation

## Features by License Type

| Feature | Trial | Full License |
|---------|-------|--------------|
| Math Node | ✅ | ✅ |
| Vision Node | ✅ | ✅ |
| Real-time Node | ✅ | ✅ |
| Language Node | ❌ | ✅ |
| Code Node | ❌ | ✅ |
| Planner Node | Limited | ✅ |
| Model Download | ❌ | ✅ |
| Query Limit | 100/day | Unlimited |
| Duration | 7 days | 90 days |
| Devices | 1 | 3 |

## API Endpoints

Once activated and running:
- `http://localhost:5002/status` - Health check
- `http://localhost:5002/nodes` - Available nodes
- `http://localhost:5002/query` - Send queries

## License Management

### Check License Status
The app shows license status on startup:
- Expiry date
- Days remaining
- License type

### Renew License
- Click "Get License" in the app
- Or visit: https://web-production-d31c0.up.railway.app/register

### Transfer License
Contact support to transfer license to new device.

## Troubleshooting

### License Key Not Working
1. Check internet connection
2. Verify key is entered correctly
3. Ensure not exceeded device limit

### App Won't Open
```bash
xattr -cr SNF-AI-Windsurf.app
```

### Reset License
Delete license file:
```bash
rm -rf SNF-AI-Windsurf.app/Contents/MacOS/.snf_ai_data
```

## Support

- Email: support@twhyne.ai
- License Portal: https://web-production-d31c0.up.railway.app
- Documentation: http://localhost:5002/docs (when running)

---
Version 3.0.0 - Licensed Edition with Activation System
© 2025 Twhyne AI. All rights reserved.
EOF
    
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✅ Licensed Executable Build Complete!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BLUE}📦 Location:${NC} dist/SNF-AI-Windsurf.app"
    echo ""
    echo -e "${YELLOW}🔐 License Features:${NC}"
    echo "   • License key activation required"
    echo "   • Online validation with Railway API"
    echo "   • 7-day trial option available"
    echo "   • 90-day full license support"
    echo "   • Multi-device support (3 devices)"
    echo "   • Offline mode with cached license"
    echo ""
    echo -e "${BLUE}📱 Workflow:${NC}"
    echo "   1. User launches app"
    echo "   2. License activation prompt"
    echo "   3. Model download (if licensed)"
    echo "   4. Full functionality unlocked"
    echo ""
    echo -e "${BLUE}🚀 To Test:${NC}"
    echo "   open dist/SNF-AI-Windsurf.app"
    echo ""
    echo -e "${GREEN}The app connects to your Railway API at:${NC}"
    echo "   https://web-production-d31c0.up.railway.app"
    echo ""
    
else
    echo -e "${RED}❌ Build failed!${NC}"
    exit 1
fi
