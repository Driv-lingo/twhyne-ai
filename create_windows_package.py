#!/usr/bin/env python3
"""
Create Windows package from the built executable
"""

import zipfile
from pathlib import Path

def create_windows_package():
    """Create the Windows package with executable and instructions."""
    project_root = Path(__file__).parent
    exe_path = project_root / "dist" / "SNF-AI-Windsurf"
    package_path = project_root / "SNF-AI-Windsurf-Windows.zip"
    
    print(f"📦 Creating Windows package: {package_path.name}")
    
    # Create installation instructions
    install_txt = Path("INSTALL_WINDOWS.txt")
    with open(install_txt, 'w') as f:
        f.write('''
SNF-AI Windsurf - Windows Installation Instructions
==================================================

🚀 QUICK START:
1. Extract this ZIP file to a folder (e.g., C:\\SNF-AI-Windsurf\\)
2. Double-click "SNF-AI-Windsurf.exe" to start
3. Your web browser will open automatically to http://localhost:5002
4. Enter your license key when prompted

📋 DETAILED STEPS:

1. EXTRACT FILES
   • Right-click the ZIP file
   • Select "Extract All..."
   • Choose a permanent location (not Downloads)

2. RUN THE APPLICATION
   • Navigate to the extracted folder
   • Double-click "SNF-AI-Windsurf.exe"
   • Windows may show a security warning - click "Run anyway"

3. FIRST TIME SETUP
   • The app will start a local web server
   • Your browser will open automatically
   • Enter your license key from https://twhyne.com
   • The app will download AI models (~8GB) on first run

🔧 TROUBLESHOOTING:

• Windows Defender Warning:
  - Click "More info" then "Run anyway"
  - Or add the folder to Windows Defender exclusions

• Port 5002 Already in Use:
  - Close other applications using port 5002
  - Or restart your computer

• Firewall Issues:
  - Allow SNF-AI-Windsurf through Windows Firewall
  - The app only uses localhost (no internet access required)

• Browser Doesn't Open:
  - Manually go to: http://localhost:5002
  - Use Chrome, Firefox, or Edge (not Internet Explorer)

📞 SUPPORT:
• Website: https://twhyne.com
• GitHub: https://github.com/Driv-lingo/twhyne-ai
• Email: support@twhyne.ai

💡 TIPS:
• Keep the console window open while using the app
• Close the console window to stop the server
• The app works completely offline after initial setup
• Your license supports up to 3 devices

''')
    
    # Create a simple batch file launcher
    launcher_bat = Path("Launch-SNF-AI.bat")
    with open(launcher_bat, 'w') as f:
        f.write('''
@echo off
echo Starting SNF-AI Windsurf...
echo.
echo If this is your first time running, please be patient
echo as the application downloads required AI models.
echo.
echo Your web browser will open automatically when ready.
echo.
echo To stop the application, close this window.
echo.
"SNF-AI-Windsurf.exe"
pause
''')
    
    # Create the ZIP package
    with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add the main executable (rename to .exe for Windows)
        zipf.write(exe_path, "SNF-AI-Windsurf.exe")
        
        # Add instructions
        zipf.write(install_txt, "INSTALL_WINDOWS.txt")
        
        # Add launcher
        zipf.write(launcher_bat, "Launch-SNF-AI.bat")
        
        # Add README if it exists
        readme_path = Path("README.md")
        if readme_path.exists():
            zipf.write(readme_path, "README.md")
    
    # Cleanup temporary files
    if install_txt.exists():
        install_txt.unlink()
    if launcher_bat.exists():
        launcher_bat.unlink()
    
    package_size = package_path.stat().st_size / (1024*1024)
    print(f"✅ Windows package created: {package_path.name}")
    print(f"📊 Package size: {package_size:.1f} MB")
    print(f"📍 Location: {package_path}")

if __name__ == "__main__":
    create_windows_package()
    print("\n🎉 Windows executable package ready!")
    print("📤 Ready to upload to GitHub Release")
