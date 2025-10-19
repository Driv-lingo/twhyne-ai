#!/usr/bin/env python3
"""
Main launcher for SNF-AI executable.
Handles license validation, model downloading and server startup.
"""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from model_downloader import check_and_download_models
from license_manager import check_and_activate_license

def get_app_dir():
    """Get the application directory."""
    if getattr(sys, 'frozen', False):
        # Running as executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))

def show_welcome():
    """Show welcome dialog."""
    root = tk.Tk()
    root.withdraw()
    
    message = """Welcome to SNF-AI Windsurf System!

This is a multi-node AI system with:
• Language Processing (requires model)
• Code Generation (requires model)
• Mathematical Calculations
• Image Processing
• Real-time Information
• Task Planning

The system will now check for required model files.
"""
    
    messagebox.showinfo("SNF-AI Windsurf", message)
    root.destroy()

def start_server(limited_mode=False):
    """Start the SNF-AI server."""
    app_dir = get_app_dir()
    
    # Show startup message
    root = tk.Tk()
    root.withdraw()
    
    if limited_mode:
        mode_text = "Limited Mode (Math, Vision, Real-time only)"
    else:
        mode_text = "Full Mode (All nodes available)"
        
    message = f"""SNF-AI Server Starting...

Mode: {mode_text}
URL: http://localhost:5002

The server is starting in the background.
You can access it at http://localhost:5002

To stop the server, close this application."""
    
    messagebox.showinfo("SNF-AI Server", message)
    root.destroy()
    
    # Import and start the server
    try:
        # Set environment variable for limited mode
        if limited_mode:
            os.environ['SNF_AI_LIMITED_MODE'] = '1'
        
        # Import the appropriate server
        if os.path.exists(os.path.join(app_dir, 'server.py')):
            from server import create_app
        else:
            from test_server import create_test_app as create_app
        
        # Create and run the app
        app = create_app()
        
        # Open browser
        import webbrowser
        webbrowser.open('http://localhost:5002')
        
        # Run the server
        app.run(host='0.0.0.0', port=5002, debug=False)
        
    except Exception as e:
        messagebox.showerror("Server Error", f"Failed to start server:\n{str(e)}")
        sys.exit(1)

def main():
    """Main entry point for the executable."""
    print("=" * 60)
    print("SNF-AI Windsurf System Launcher")
    print("=" * 60)
    
    # Step 1: License validation (required)
    print("Checking license...")
    activated = check_and_activate_license()
    
    if not activated:
        messagebox.showerror(
            "License Required",
            "A valid license is required to use SNF-AI Windsurf.\n\n"
            "Please purchase a license at:\n"
            "https://web-production-d31c0.up.railway.app/register\n\n"
            "Then enter your license key to activate."
        )
        sys.exit(1)
    
    # Show welcome on first run
    first_run_flag = os.path.join(get_app_dir(), '.first_run_complete')
    if not os.path.exists(first_run_flag):
        show_welcome()
        Path(first_run_flag).touch()
    
    # Step 2: Check and download models (for licensed users)
    print("Checking models...")
    models_dir = os.path.join(get_app_dir(), 'models')
    models_available = check_and_download_models(models_dir)
    
    # Step 3: Start server with appropriate mode
    if models_available:
        print("✓ Models available - starting in full mode")
        start_server(limited_mode=False)
    else:
        print("⚠ Models not available - starting in limited mode")
        print("  (Math, Vision, and Real-time nodes only)")
        start_server(limited_mode=True)

if __name__ == '__main__':
    main()
