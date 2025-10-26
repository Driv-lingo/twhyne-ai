#!/bin/bash

# Build script for creating macOS executable of SNF-AI system
# This creates a standalone app with all nodes included

echo "🔨 Building SNF-AI macOS Executable..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo -e "${YELLOW}PyInstaller not found. Installing...${NC}"
    pip install pyinstaller
fi

# Create a spec file for the full system
cat > snf_ai_full.spec << 'EOF'
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Analysis for the full SNF-AI system
a = Analysis(
    ['backend/test_server.py'],  # Using test_server for now, replace with server.py when ready
    pathex=['backend'],
    binaries=[],
    datas=[
        ('backend/flux_nodes', 'flux_nodes'),
        ('models/.gitkeep', 'models'),
        ('uploads/.gitkeep', 'uploads'),
        ('frontend/build', 'frontend/build'),  # Include frontend if built
    ],
    hiddenimports=[
        'flask',
        'flask_cors',
        'PIL',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    console=True,  # Set to False for production
    disable_windowed_traceback=False,
    argv_emulation=False,
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
        'CFBundleGetInfoString': "SNF-AI Windsurf - Multi-Node AI System",
        'CFBundleIdentifier': 'com.twhyne.snf-ai',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '10.15.0',
    }
)
EOF

echo -e "${GREEN}✅ Created PyInstaller spec file${NC}"

# Build the executable
echo "🚀 Building executable..."
pyinstaller --clean --noconfirm snf_ai_full.spec

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Build successful!${NC}"
    echo ""
    echo "📦 Executable created at: dist/SNF-AI-Windsurf.app"
    echo ""
    echo -e "${YELLOW}⚠️  Important Notes:${NC}"
    echo "1. This build uses the test_server.py (lightweight version)"
    echo "2. For full functionality with all nodes, you'll need:"
    echo "   - Language Node: mistral-7b-instruct-v0.2.Q4_K_M.gguf"
    echo "   - Code Node: codellama-7b.Q4_K_M.gguf"
    echo "3. Place model files in: dist/SNF-AI-Windsurf.app/Contents/MacOS/models/"
    echo ""
    echo "4. Currently included nodes (work without models):"
    echo "   ✅ Math Node - Mathematical calculations"
    echo "   ✅ Vision Node - Image processing"
    echo "   ✅ Real-time Node - Current time/date"
    echo ""
    echo "5. To run the app:"
    echo "   open dist/SNF-AI-Windsurf.app"
    echo "   or"
    echo "   ./dist/SNF-AI-Windsurf.app/Contents/MacOS/SNF-AI-Windsurf"
else
    echo -e "${RED}❌ Build failed!${NC}"
    exit 1
fi
