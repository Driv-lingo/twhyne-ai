#!/usr/bin/env python3
"""
Model downloader for SNF-AI system.
Downloads required GGUF model files from Hugging Face on first run.
"""

import os
import sys
import hashlib
import requests
from pathlib import Path
from typing import Optional, Dict, Tuple
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

# Model configurations
MODELS = {
    'mistral': {
        'name': 'mistral-7b-instruct-v0.2.Q4_K_M.gguf',
        'url': 'https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf',
        'size': '4.37 GB',
        'size_bytes': 4689856512,
        'sha256': 'c5db93de89b89c0f5fb1e7b0e48dc64e98e6f8ce5b4c5b0e23d3d0c8ec3c8e3f',  # Example hash
        'description': 'Language understanding and generation'
    },
    'codellama': {
        'name': 'codellama-7b.Q4_K_M.gguf',
        'url': 'https://huggingface.co/TheBloke/CodeLlama-7B-GGUF/resolve/main/codellama-7b.Q4_K_M.gguf',
        'size': '4.08 GB',
        'size_bytes': 4379365376,
        'sha256': 'd4b09e3e8a4b09e3e8a4b09e3e8a4b09e3e8a4b09e3e8a4b09e3e8a4b09e3e8a4',  # Example hash
        'description': 'Code analysis and generation'
    }
}

class ModelDownloaderGUI:
    """GUI for downloading models with progress tracking."""
    
    def __init__(self, models_dir: str):
        self.models_dir = models_dir
        self.root = tk.Tk()
        self.root.title("SNF-AI Model Downloader")
        self.root.geometry("600x400")
        self.root.resizable(False, False)
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.root.winfo_screenheight() // 2) - (400 // 2)
        self.root.geometry(f'+{x}+{y}')
        
        self.setup_ui()
        self.download_cancelled = False
        
    def setup_ui(self):
        """Setup the user interface."""
        # Title
        title = tk.Label(self.root, text="SNF-AI Model Setup", font=("Arial", 20, "bold"))
        title.pack(pady=20)
        
        # Info text
        info_text = """The following AI models are required for full functionality:
        
• Mistral 7B (4.37 GB) - Language understanding
• CodeLlama 7B (4.08 GB) - Code generation

Without these models, only Math, Vision, and Real-time nodes will work."""
        
        info_label = tk.Label(self.root, text=info_text, justify=tk.LEFT)
        info_label.pack(pady=10, padx=20)
        
        # Progress frame
        self.progress_frame = tk.Frame(self.root)
        self.progress_frame.pack(pady=20, padx=20, fill=tk.X)
        
        self.status_label = tk.Label(self.progress_frame, text="Ready to download")
        self.status_label.pack()
        
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, 
            length=560, 
            mode='determinate'
        )
        self.progress_bar.pack(pady=10)
        
        self.speed_label = tk.Label(self.progress_frame, text="")
        self.speed_label.pack()
        
        # Buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=20)
        
        self.download_btn = tk.Button(
            button_frame,
            text="Download Models",
            command=self.start_download,
            bg="#4CAF50",
            fg="white",
            padx=20,
            pady=10
        )
        self.download_btn.pack(side=tk.LEFT, padx=10)
        
        self.skip_btn = tk.Button(
            button_frame,
            text="Skip (Limited Mode)",
            command=self.skip_download,
            padx=20,
            pady=10
        )
        self.skip_btn.pack(side=tk.LEFT, padx=10)
        
        self.cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=self.cancel_download,
            state=tk.DISABLED,
            padx=20,
            pady=10
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=10)
        
    def start_download(self):
        """Start downloading models in a separate thread."""
        self.download_btn.config(state=tk.DISABLED)
        self.skip_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        self.download_cancelled = False
        
        # Start download in background thread
        thread = threading.Thread(target=self.download_models)
        thread.daemon = True
        thread.start()
        
    def download_models(self):
        """Download all required models."""
        try:
            for model_key, model_info in MODELS.items():
                if self.download_cancelled:
                    break
                    
                model_path = os.path.join(self.models_dir, model_info['name'])
                
                # Check if already exists
                if os.path.exists(model_path):
                    self.update_status(f"✓ {model_info['name']} already exists")
                    continue
                
                # Download model
                self.update_status(f"Downloading {model_info['name']} ({model_info['size']})...")
                success = self.download_file(
                    model_info['url'],
                    model_path,
                    model_info['size_bytes']
                )
                
                if success:
                    self.update_status(f"✓ Downloaded {model_info['name']}")
                else:
                    if not self.download_cancelled:
                        self.update_status(f"✗ Failed to download {model_info['name']}")
                        
            if not self.download_cancelled:
                self.download_complete()
                
        except Exception as e:
            self.update_status(f"Error: {str(e)}")
            messagebox.showerror("Download Error", str(e))
            
    def download_file(self, url: str, filepath: str, total_size: int) -> bool:
        """Download a file with progress tracking."""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            downloaded = 0
            chunk_size = 8192
            start_time = time.time()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if self.download_cancelled:
                        os.remove(filepath)
                        return False
                        
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress
                        progress = (downloaded / total_size) * 100
                        self.progress_bar['value'] = progress
                        
                        # Calculate speed
                        elapsed = time.time() - start_time
                        if elapsed > 0:
                            speed = downloaded / elapsed / 1024 / 1024  # MB/s
                            remaining = (total_size - downloaded) / (downloaded / elapsed)
                            self.speed_label.config(
                                text=f"Speed: {speed:.1f} MB/s | ETA: {int(remaining)}s"
                            )
                        
                        self.root.update_idletasks()
                        
            return True
            
        except Exception as e:
            print(f"Download error: {e}")
            return False
            
    def update_status(self, message: str):
        """Update status label."""
        self.status_label.config(text=message)
        self.root.update_idletasks()
        
    def download_complete(self):
        """Handle download completion."""
        self.update_status("✓ All models downloaded successfully!")
        self.progress_bar['value'] = 100
        messagebox.showinfo(
            "Download Complete",
            "All models have been downloaded successfully!\n\nThe application will now start with full functionality."
        )
        self.root.destroy()
        
    def skip_download(self):
        """Skip download and run in limited mode."""
        result = messagebox.askyesno(
            "Skip Download?",
            "Without models, only Math, Vision, and Real-time nodes will work.\n\nContinue in limited mode?"
        )
        if result:
            self.root.destroy()
            
    def cancel_download(self):
        """Cancel ongoing download."""
        self.download_cancelled = True
        self.update_status("Download cancelled")
        self.cancel_btn.config(state=tk.DISABLED)
        self.download_btn.config(state=tk.NORMAL)
        self.skip_btn.config(state=tk.NORMAL)
        self.progress_bar['value'] = 0
        self.speed_label.config(text="")
        
    def run(self) -> bool:
        """Run the GUI and return whether models are available."""
        self.root.mainloop()
        
        # Check if models exist after GUI closes
        for model_info in MODELS.values():
            model_path = os.path.join(self.models_dir, model_info['name'])
            if os.path.exists(model_path):
                return True
        return False


def check_and_download_models(models_dir: str = None) -> bool:
    """
    Check for models and download if needed.
    Returns True if models are available, False otherwise.
    """
    if models_dir is None:
        # Determine models directory based on execution context
        if getattr(sys, 'frozen', False):
            # Running as executable
            models_dir = os.path.join(os.path.dirname(sys.executable), 'models')
        else:
            # Running as script
            models_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
            
    models_dir = os.path.abspath(models_dir)
    os.makedirs(models_dir, exist_ok=True)
    
    # Check if models already exist
    models_exist = True
    for model_info in MODELS.values():
        model_path = os.path.join(models_dir, model_info['name'])
        if not os.path.exists(model_path):
            models_exist = False
            break
            
    if models_exist:
        print("✓ All models found")
        return True
        
    # Show download GUI
    print("Models not found. Starting download interface...")
    downloader = ModelDownloaderGUI(models_dir)
    return downloader.run()


def download_models_cli(models_dir: str = None) -> bool:
    """
    Command-line version of model downloader.
    """
    if models_dir is None:
        models_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
        
    models_dir = os.path.abspath(models_dir)
    os.makedirs(models_dir, exist_ok=True)
    
    print("=" * 60)
    print("SNF-AI Model Downloader")
    print("=" * 60)
    
    for model_key, model_info in MODELS.items():
        model_path = os.path.join(models_dir, model_info['name'])
        
        if os.path.exists(model_path):
            print(f"✓ {model_info['name']} already exists")
            continue
            
        print(f"\nDownloading {model_info['name']} ({model_info['size']})...")
        print(f"From: {model_info['url']}")
        
        try:
            response = requests.get(model_info['url'], stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(model_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Show progress
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\rProgress: {progress:.1f}%", end='')
                            
            print(f"\n✓ Downloaded {model_info['name']}")
            
        except Exception as e:
            print(f"\n✗ Failed to download {model_info['name']}: {e}")
            return False
            
    print("\n✓ All models downloaded successfully!")
    return True


if __name__ == '__main__':
    # Test the downloader
    import argparse
    parser = argparse.ArgumentParser(description='Download SNF-AI models')
    parser.add_argument('--cli', action='store_true', help='Use CLI instead of GUI')
    parser.add_argument('--dir', help='Models directory', default='../models')
    args = parser.parse_args()
    
    if args.cli:
        success = download_models_cli(args.dir)
    else:
        success = check_and_download_models(args.dir)
        
    sys.exit(0 if success else 1)
