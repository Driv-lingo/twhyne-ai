#!/usr/bin/env python3
"""
Build script for creating a macOS executable of the full SNF-AI system.
This creates a standalone app with all nodes included (except RAG test databases).
"""

import os
import sys
import shutil
import subprocess

def build_executable():
    """Build the macOS executable with all nodes."""
    
    print("🔨 Building SNF-AI macOS Executable...")
    
    # PyInstaller spec file content
    spec_content = """
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['backend/server.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('backend/flux_nodes/*.py', 'flux_nodes'),
        ('backend/*.py', '.'),
        ('models/.gitkeep', 'models'),
        ('uploads/.gitkeep', 'uploads'),
    ],
    hiddenimports=[
        'flask',
        'flask_cors',
        'PIL',
        'numpy',
        'logging',
        'pathlib',
        'typing',
        'backend.flux_nodes.base',
        'backend.flux_nodes.language',
        'backend.flux_nodes.code',
        'backend.flux_nodes.math',
        'backend.flux_nodes.planner',
        'backend.flux_nodes.vision',
        'backend.rag_manager',
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
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
"""
    
    # Write spec file
    with open('snf_ai.spec', 'w') as f:
        f.write(spec_content)
    
    print("📝 Created PyInstaller spec file")
    
    # Create startup wrapper to handle model files
    wrapper_content = '''#!/usr/bin/env python3
"""
Startup wrapper for SNF-AI executable.
Handles model file checks and provides user feedback.
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox
import subprocess

def check_models():
    """Check if model files exist."""
    models_dir = os.path.join(os.path.dirname(sys.executable), 'models')
    
    # Check for model files
    required_models = [
        'mistral-7b-instruct-v0.2.Q4_K_M.gguf',
        'codellama-7b.Q4_K_M.gguf'
    ]
    
    missing_models = []
    for model in required_models:
        model_path = os.path.join(models_dir, model)
        if not os.path.exists(model_path):
            missing_models.append(model)
    
    return missing_models

def show_model_warning(missing_models):
    """Show warning about missing models."""
    root = tk.Tk()
    root.withdraw()
    
    message = "The following model files are missing:\\n\\n"
    message += "\\n".join(f"• {model}" for model in missing_models)
    message += "\\n\\nThe app will run with limited functionality.\\n"
    message += "Only Math, Vision, and Real-time nodes will be available.\\n\\n"
    message += "To enable full functionality, download the model files from:\\n"
    message += "https://huggingface.co/TheBloke"
    
    result = messagebox.askquestion(
        "Missing Model Files",
        message + "\\n\\nDo you want to continue anyway?",
        icon='warning'
    )
    
    root.destroy()
    return result == 'yes'

def main():
    """Main entry point."""
    missing_models = check_models()
    
    if missing_models:
        if not show_model_warning(missing_models):
            sys.exit(0)
    
    # Import and run the actual server
    from backend import server
    server.main()

if __name__ == '__main__':
    main()
'''
    
    with open('backend/app_wrapper.py', 'w') as f:
        f.write(wrapper_content)
    
    print("🎯 Created app wrapper for model checking")
    
    # Build command
    build_cmd = [
        'pyinstaller',
        '--clean',
        '--noconfirm',
        'snf_ai.spec'
    ]
    
    print("🚀 Running PyInstaller...")
    try:
        subprocess.run(build_cmd, check=True)
        print("✅ Build successful!")
        
        # Create models directory in the app
        app_path = 'dist/SNF-AI-Windsurf.app'
        models_dir = os.path.join(app_path, 'Contents', 'MacOS', 'models')
        os.makedirs(models_dir, exist_ok=True)
        
        # Create README for models
        readme_content = """# Model Files Required

This app requires the following model files to be placed in this directory:

1. mistral-7b-instruct-v0.2.Q4_K_M.gguf (~4.4GB)
2. codellama-7b.Q4_K_M.gguf (~4.1GB)

Download from: https://huggingface.co/TheBloke

Without these files, only Math, Vision, and Real-time nodes will work.
"""
        
        with open(os.path.join(models_dir, 'README.md'), 'w') as f:
            f.write(readme_content)
        
        print(f"📦 App created at: {app_path}")
        print("📝 Note: Model files need to be added to the models/ directory")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    build_executable()
