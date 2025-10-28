#!/bin/bash
# Build SNF-AI Manager for distribution

set -e

echo "Building SNF-AI Manager Desktop Application"
echo "==========================================="

# Install PyInstaller if not present
pip install pyinstaller pillow

# Create icon (optional)
python3 << EOF
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGB', (256, 256), color='#2563eb')
draw = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80)
except:
    font = ImageFont.load_default()
draw.text((128, 128), "SNF", fill='white', anchor='mm', font=font)
img.save('icon.png')
print("Icon created")
EOF

# Build for current platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Building for macOS..."
    pyinstaller --onefile --windowed \
        --name "SNF-AI Manager" \
        --icon icon.png \
        --add-data "icon.png:." \
        --hidden-import tkinter \
        --hidden-import subprocess \
        --hidden-import webbrowser \
        snf-ai-manager.py
    
    # Create DMG
    echo "Creating DMG installer..."
    mkdir -p dist/dmg
    cp -r "dist/SNF-AI Manager.app" dist/dmg/
    
    # Create simple DMG
    hdiutil create -volname "SNF-AI Manager" \
        -srcfolder dist/dmg \
        -ov -format UDZO \
        "dist/SNF-AI-Manager-Mac.dmg"
    
    echo "✅ Mac app created: dist/SNF-AI-Manager-Mac.dmg"
    
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
    echo "Building for Windows..."
    pyinstaller --onefile --windowed \
        --name "SNF-AI-Manager" \
        --icon icon.ico \
        --add-data "icon.ico;." \
        --hidden-import tkinter \
        --hidden-import subprocess \
        --hidden-import webbrowser \
        snf-ai-manager.py
    
    echo "✅ Windows exe created: dist/SNF-AI-Manager.exe"
    
else
    echo "Building for Linux..."
    pyinstaller --onefile \
        --name "snf-ai-manager" \
        --add-data "icon.png:." \
        --hidden-import tkinter \
        --hidden-import subprocess \
        --hidden-import webbrowser \
        snf-ai-manager.py
    
    # Create AppImage (optional)
    echo "✅ Linux binary created: dist/snf-ai-manager"
fi

echo ""
echo "Build complete!"
echo ""
echo "Distribution files:"
ls -la dist/
