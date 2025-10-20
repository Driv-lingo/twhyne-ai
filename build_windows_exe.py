#!/usr/bin/env python3
"""
Windows Executable Builder for SNF-AI Windsurf
Uses PyInstaller to create a proper .exe file
"""

import os
import sys
import subprocess
import shutil
import zipfile
from pathlib import Path

def build_windows_exe():
    """Build Windows executable using PyInstaller."""
    print("🔨 Building Windows executable for SNF-AI Windsurf...")
    
    # Ensure we're in the right directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Install PyInstaller if not available
    try:
        import PyInstaller
        print("✓ PyInstaller already installed")
    except ImportError:
        print("📦 Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("✓ PyInstaller installed")
    
    # Create the main entry point script
    main_script = project_root / "snf_ai_windows_main.py"
    print("📝 Creating Windows entry point...")
    
    with open(main_script, 'w') as f:
        f.write('''
#!/usr/bin/env python3
"""
SNF-AI Windsurf Windows Entry Point
"""

import sys
import os
import time
import webbrowser
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

def main():
    """Main entry point for SNF-AI Windsurf on Windows."""
    print("="*60)
    print("🚀 SNF-AI Windsurf - Starting...")
    print("="*60)
    print("📊 Dashboard will be available at: http://localhost:5002/")
    print("🔧 API endpoint: http://localhost:5002/query")
    print("📝 Status endpoint: http://localhost:5002/status")
    print("="*60)
    print("")
    print("⏳ Starting server... (this may take a moment)")
    
    try:
        # Check if models exist, if not, inform user
        models_dir = Path(__file__).parent / "models"
        model_files = list(models_dir.glob("*.gguf"))
        
        if not model_files:
            print("⚠️  AI models not found. The app will run in limited mode.")
            print("📥 To download models, visit: https://twhyne.com")
            print("")
        
        # Import and run the server
        from server import create_app
        app = create_app()
        
        print("✅ Server started successfully!")
        print("🌐 Opening web browser...")
        
        # Open browser after a short delay
        import threading
        def open_browser():
            time.sleep(2)
            webbrowser.open('http://localhost:5002')
        
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        
        print("")
        print("🎯 SNF-AI Windsurf is now running!")
        print("💡 Close this window to stop the server")
        print("")
        
        # Run the Flask app
        app.run(host='0.0.0.0', port=5002, debug=False)
        
    except ImportError as e:
        print(f"❌ Error importing server: {e}")
        print("Please ensure all dependencies are installed.")
        input("Press Enter to exit...")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        print("")
        print("🔧 Troubleshooting:")
        print("   • Make sure port 5002 is not in use")
        print("   • Check Windows Firewall settings")
        print("   • Try running as Administrator")
        print("")
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()
''')
    
    print("✓ Entry point created")
    
    # Build the executable using PyInstaller
    print("🔨 Running PyInstaller...")
    
    # Determine the correct separator for add-data based on platform
    import platform
    if platform.system() == "Windows":
        data_sep = ";"
    else:
        data_sep = ":"
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                    # Single executable file
        "--console",                    # Show console window
        "--name", "SNF-AI-Windsurf",    # Executable name
        "--add-data", f"backend{data_sep}backend", # Include backend folder
        "--add-data", f"models/.gitkeep{data_sep}models", # Include models folder structure only
        "--add-data", f"uploads/.gitkeep{data_sep}uploads", # Include uploads folder structure only
        "--hidden-import", "flask",
        "--hidden-import", "flask_cors",
        "--hidden-import", "PIL",
        "--hidden-import", "numpy",
        "--hidden-import", "requests",
        "--exclude-module", "matplotlib", # Exclude heavy modules
        "--exclude-module", "scipy",
        "--exclude-module", "pandas",
        str(main_script)
    ]
    
    print("📋 PyInstaller command:")
    print(" ".join(cmd))
    print("")
    
    # Run PyInstaller without capturing output so we can see progress
    print("⏳ This may take 2-5 minutes... Please wait...")
    result = subprocess.run(cmd)
    
    try:
        if result.returncode == 0:
            print("✅ Windows executable built successfully!")
            
            # Check for both .exe and no extension (macOS creates without .exe)
            exe_path = project_root / "dist" / "SNF-AI-Windsurf.exe"
            if not exe_path.exists():
                exe_path = project_root / "dist" / "SNF-AI-Windsurf"
            if exe_path.exists():
                file_size = exe_path.stat().st_size / (1024*1024)
                print(f"📦 Executable location: {exe_path}")
                print(f"📊 File size: {file_size:.1f} MB")
                
                # Create Windows package
                windows_package = project_root / "SNF-AI-Windsurf-Windows.zip"
                create_windows_package(exe_path, windows_package)
                
                return True
            else:
                print("❌ Executable not found in expected location")
                return False
        else:
            print("❌ PyInstaller failed!")
            print("Check the output above for error details.")
            return False
    
    finally:
        # Cleanup temporary files
        if main_script.exists():
            main_script.unlink()
            print("🧹 Cleaned up temporary files")

def create_windows_package(exe_path, package_path):
    """Create a Windows package with the executable and instructions."""
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
    
    # Create a simple batch file launcher (alternative method)
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
    print("🏗️  SNF-AI Windsurf Windows Builder")
    print("="*50)
    
    success = build_windows_exe()
    
    if success:
        print("")
        print("🎉 Windows executable build completed successfully!")
        print("📤 Ready to upload to GitHub Release")
        print("")
        print("📋 Next steps:")
        print("   1. Test the executable on a Windows machine")
        print("   2. Upload SNF-AI-Windsurf-Windows.zip to GitHub Release")
        print("   3. Update download page to point to new Windows package")
    else:
        print("")
        print("❌ Windows executable build failed")
        print("🔧 Check the error messages above for details")
        sys.exit(1)
