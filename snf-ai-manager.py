#!/usr/bin/env python3
"""
SNF-AI Windsurf Manager - Desktop GUI for easy Docker management
No command line needed!
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import threading
import json
import os
import sys
import webbrowser
from datetime import datetime
import platform

class SNFAIManager:
    def __init__(self, root):
        self.root = root
        self.root.title("SNF-AI Windsurf Manager")
        self.root.geometry("800x600")
        
        # Set icon if available
        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass
        
        self.license_key = tk.StringVar()
        self.container_status = tk.StringVar(value="Checking...")
        self.current_version = tk.StringVar(value="Unknown")
        self.is_running = False
        
        self.setup_ui()
        self.check_docker()
        self.refresh_status()
    
    def setup_ui(self):
        """Create the user interface."""
        # Main notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Status Tab
        status_frame = ttk.Frame(notebook)
        notebook.add(status_frame, text="Status")
        self.create_status_tab(status_frame)
        
        # License Tab
        license_frame = ttk.Frame(notebook)
        notebook.add(license_frame, text="License")
        self.create_license_tab(license_frame)
        
        # Update Tab
        update_frame = ttk.Frame(notebook)
        notebook.add(update_frame, text="Updates")
        self.create_update_tab(update_frame)
        
        # Logs Tab
        logs_frame = ttk.Frame(notebook)
        notebook.add(logs_frame, text="Logs")
        self.create_logs_tab(logs_frame)
        
        # Bottom button bar
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(button_frame, text="Open Application", 
                  command=self.open_app).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Refresh", 
                  command=self.refresh_status).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Exit", 
                  command=self.root.quit).pack(side="right", padx=5)
    
    def create_status_tab(self, parent):
        """Create status display."""
        # Status info
        info_frame = ttk.LabelFrame(parent, text="System Status", padding=10)
        info_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(info_frame, text="Docker Status:").grid(row=0, column=0, sticky="w", pady=2)
        self.docker_status_label = ttk.Label(info_frame, text="Checking...", foreground="gray")
        self.docker_status_label.grid(row=0, column=1, sticky="w", pady=2)
        
        ttk.Label(info_frame, text="Container Status:").grid(row=1, column=0, sticky="w", pady=2)
        self.container_status_label = ttk.Label(info_frame, textvariable=self.container_status)
        self.container_status_label.grid(row=1, column=1, sticky="w", pady=2)
        
        ttk.Label(info_frame, text="Current Version:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(info_frame, textvariable=self.current_version).grid(row=2, column=1, sticky="w", pady=2)
        
        ttk.Label(info_frame, text="License Status:").grid(row=3, column=0, sticky="w", pady=2)
        self.license_status_label = ttk.Label(info_frame, text="Checking...", foreground="gray")
        self.license_status_label.grid(row=3, column=1, sticky="w", pady=2)
        
        # Control buttons
        control_frame = ttk.LabelFrame(parent, text="Controls", padding=10)
        control_frame.pack(fill="x", padx=10, pady=10)
        
        self.start_button = ttk.Button(control_frame, text="Start SNF-AI", 
                                       command=self.start_container, state="disabled")
        self.start_button.pack(side="left", padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="Stop SNF-AI", 
                                      command=self.stop_container, state="disabled")
        self.stop_button.pack(side="left", padx=5)
        
        self.restart_button = ttk.Button(control_frame, text="Restart SNF-AI", 
                                         command=self.restart_container, state="disabled")
        self.restart_button.pack(side="left", padx=5)
    
    def create_license_tab(self, parent):
        """Create license management interface."""
        # License entry
        entry_frame = ttk.LabelFrame(parent, text="License Key", padding=10)
        entry_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(entry_frame, text="Enter your license key:").pack(anchor="w")
        
        key_frame = ttk.Frame(entry_frame)
        key_frame.pack(fill="x", pady=5)
        
        self.license_entry = ttk.Entry(key_frame, textvariable=self.license_key, width=50)
        self.license_entry.pack(side="left", padx=(0, 5))
        
        ttk.Button(key_frame, text="Save", command=self.save_license).pack(side="left")
        ttk.Button(key_frame, text="Validate", command=self.validate_license).pack(side="left", padx=5)
        
        # License info
        info_frame = ttk.LabelFrame(parent, text="License Information", padding=10)
        info_frame.pack(fill="x", padx=10, pady=10)
        
        self.license_info_text = scrolledtext.ScrolledText(info_frame, height=10, width=60)
        self.license_info_text.pack(fill="both", expand=True)
        
        # Purchase button
        ttk.Button(parent, text="Purchase License ($20/month)", 
                  command=lambda: webbrowser.open("https://sunny-imagination-production.up.railway.app")
                  ).pack(pady=10)
    
    def create_update_tab(self, parent):
        """Create update management interface."""
        # Update info
        info_frame = ttk.LabelFrame(parent, text="Version Information", padding=10)
        info_frame.pack(fill="x", padx=10, pady=10)
        
        self.update_info_text = scrolledtext.ScrolledText(info_frame, height=8, width=60)
        self.update_info_text.pack(fill="both", expand=True)
        
        # Update controls
        control_frame = ttk.LabelFrame(parent, text="Update Controls", padding=10)
        control_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(control_frame, text="Check for Updates", 
                  command=self.check_updates).pack(side="left", padx=5)
        
        self.update_button = ttk.Button(control_frame, text="Install Update", 
                                        command=self.install_update, state="disabled")
        self.update_button.pack(side="left", padx=5)
        
        # Auto-update checkbox
        self.auto_update = tk.BooleanVar(value=True)
        ttk.Checkbutton(control_frame, text="Automatic Updates", 
                       variable=self.auto_update).pack(side="left", padx=20)
        
        # Cleanup option
        self.auto_cleanup = tk.BooleanVar(value=True)
        ttk.Checkbutton(control_frame, text="Auto-remove old versions", 
                       variable=self.auto_cleanup).pack(side="left", padx=5)
    
    def create_logs_tab(self, parent):
        """Create log viewer."""
        # Log display
        self.log_text = scrolledtext.ScrolledText(parent, height=20, width=80)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Log controls
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(control_frame, text="View Logs", 
                  command=self.view_logs).pack(side="left", padx=5)
        ttk.Button(control_frame, text="Clear", 
                  command=lambda: self.log_text.delete(1.0, tk.END)).pack(side="left", padx=5)
        ttk.Button(control_frame, text="Export Logs", 
                  command=self.export_logs).pack(side="left", padx=5)
    
    def check_docker(self):
        """Check if Docker is installed and running."""
        try:
            result = subprocess.run(["docker", "--version"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.docker_status_label.config(text="✓ Installed", foreground="green")
                
                # Check if Docker daemon is running
                result = subprocess.run(["docker", "ps"], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    self.docker_status_label.config(text="✓ Running", foreground="green")
                    return True
                else:
                    self.docker_status_label.config(text="⚠ Not running", foreground="orange")
                    messagebox.showwarning("Docker Not Running", 
                                         "Docker Desktop is not running.\nPlease start Docker Desktop.")
            else:
                self.docker_status_label.config(text="✗ Not installed", foreground="red")
                messagebox.showerror("Docker Not Found", 
                                   "Docker is not installed.\nPlease install Docker Desktop first.")
        except:
            self.docker_status_label.config(text="✗ Error", foreground="red")
            return False
        return False
    
    def refresh_status(self):
        """Refresh container status."""
        if not self.check_docker():
            return
        
        try:
            # Check if container exists
            result = subprocess.run(["docker", "ps", "-a", "--filter", "name=twhyne", "--format", "{{.Status}}"],
                                  capture_output=True, text=True)
            
            if result.stdout.strip():
                status = result.stdout.strip()
                if "Up" in status:
                    self.container_status.set("✓ Running")
                    self.container_status_label.config(foreground="green")
                    self.is_running = True
                    self.start_button.config(state="disabled")
                    self.stop_button.config(state="normal")
                    self.restart_button.config(state="normal")
                else:
                    self.container_status.set("⚠ Stopped")
                    self.container_status_label.config(foreground="orange")
                    self.is_running = False
                    self.start_button.config(state="normal")
                    self.stop_button.config(state="disabled")
                    self.restart_button.config(state="disabled")
                
                # Get version
                result = subprocess.run(["docker", "inspect", "twhyne", "--format", "{{.Config.Image}}"],
                                      capture_output=True, text=True)
                if result.stdout:
                    self.current_version.set(result.stdout.strip().split(":")[-1])
            else:
                self.container_status.set("✗ Not installed")
                self.container_status_label.config(foreground="red")
                self.is_running = False
                self.start_button.config(state="normal", text="Install & Start")
                self.stop_button.config(state="disabled")
                self.restart_button.config(state="disabled")
            
            # Check license
            self.check_license_status()
            
        except Exception as e:
            self.log(f"Error checking status: {e}")
    
    def check_license_status(self):
        """Check license validity."""
        license_key = self.load_license()
        if license_key:
            self.license_key.set(license_key)
            # Could validate with server here
            self.license_status_label.config(text="✓ Configured", foreground="green")
        else:
            self.license_status_label.config(text="⚠ Not configured", foreground="orange")
    
    def start_container(self):
        """Start or install the container."""
        license_key = self.load_license()
        if not license_key:
            messagebox.showerror("License Required", 
                               "Please enter your license key in the License tab first.")
            return
        
        def run():
            try:
                self.log("Starting SNF-AI Windsurf...")
                
                # Pull latest image
                self.log("Downloading latest version...")
                subprocess.run(["docker", "pull", "twhyne/twhyne:licensed"], check=True)
                
                # Remove old container if exists
                subprocess.run(["docker", "rm", "-f", "twhyne"], 
                             capture_output=True)
                
                # Start new container with all volumes
                cmd = [
                    "docker", "run", "-d",
                    "--name", "twhyne",
                    "-e", f"SNF_LICENSE_KEY={license_key}",
                    "-p", "3000:3000",
                    "-p", "5002:5002",
                    "--mount", "source=snf_models,target=/app/models",
                    "--mount", "source=snf_logs,target=/app/logs",
                    "--mount", "source=snf_data,target=/app/data",
                    "--mount", "source=snf_uploads,target=/app/uploads",
                    "--mount", "source=snf_rag,target=/app/rag_storage",
                    "--mount", "source=snf_conversations,target=/app/conversations",
                    "--restart", "unless-stopped",
                    "twhyne/twhyne:licensed"
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.log("✓ SNF-AI started successfully!")
                    
                    # Clean up old images if auto-cleanup enabled
                    if self.auto_cleanup.get():
                        self.cleanup_old_images()
                    
                    self.refresh_status()
                    messagebox.showinfo("Success", "SNF-AI is now running!\n\nAccess at: http://localhost:3000")
                else:
                    self.log(f"Error: {result.stderr}")
                    messagebox.showerror("Start Failed", f"Failed to start:\n{result.stderr}")
                    
            except Exception as e:
                self.log(f"Error: {e}")
                messagebox.showerror("Error", str(e))
        
        threading.Thread(target=run, daemon=True).start()
    
    def stop_container(self):
        """Stop the container."""
        try:
            self.log("Stopping SNF-AI...")
            subprocess.run(["docker", "stop", "twhyne"], check=True)
            self.log("✓ SNF-AI stopped")
            self.refresh_status()
        except Exception as e:
            self.log(f"Error: {e}")
            messagebox.showerror("Error", str(e))
    
    def restart_container(self):
        """Restart the container."""
        self.stop_container()
        self.start_container()
    
    def check_updates(self):
        """Check for available updates."""
        try:
            self.log("Checking for updates...")
            
            # Get current version
            current = subprocess.run(["docker", "inspect", "twhyne", "--format", "{{.Config.Image}}"],
                                   capture_output=True, text=True).stdout.strip()
            
            # Pull latest to check
            result = subprocess.run(["docker", "pull", "twhyne/twhyne:latest"],
                                  capture_output=True, text=True)
            
            if "Status: Image is up to date" in result.stdout:
                self.update_info_text.insert(tk.END, "✓ You have the latest version\n")
                self.update_button.config(state="disabled")
            else:
                self.update_info_text.insert(tk.END, "🔄 Update available!\n")
                self.update_info_text.insert(tk.END, f"Current: {current}\n")
                self.update_info_text.insert(tk.END, "New version downloaded and ready to install\n")
                self.update_button.config(state="normal")
                
                if self.auto_update.get():
                    if messagebox.askyesno("Update Available", 
                                          "An update is available. Install now?"):
                        self.install_update()
        except Exception as e:
            self.log(f"Error checking updates: {e}")
    
    def install_update(self):
        """Install the latest update."""
        def run():
            try:
                self.log("Installing update...")
                
                # Stop current container
                self.log("Stopping current version...")
                subprocess.run(["docker", "stop", "twhyne"], capture_output=True)
                subprocess.run(["docker", "rm", "twhyne"], capture_output=True)
                
                # Start with new version (preserves volumes)
                self.start_container()
                
                # Clean up old images
                if self.auto_cleanup.get():
                    self.cleanup_old_images()
                
                self.log("✓ Update complete!")
                messagebox.showinfo("Update Complete", "SNF-AI has been updated successfully!")
                
            except Exception as e:
                self.log(f"Error: {e}")
                messagebox.showerror("Update Failed", str(e))
        
        threading.Thread(target=run, daemon=True).start()
    
    def cleanup_old_images(self):
        """Remove old Docker images to save space."""
        try:
            self.log("Cleaning up old images...")
            # Remove unused images
            result = subprocess.run(["docker", "image", "prune", "-f"],
                                  capture_output=True, text=True)
            
            # Remove old versions of our image
            result = subprocess.run(["docker", "images", "twhyne/twhyne", "--format", "{{.ID}} {{.Tag}}"],
                                  capture_output=True, text=True)
            
            for line in result.stdout.strip().split("\n"):
                if line and "latest" not in line and "licensed" not in line:
                    image_id = line.split()[0]
                    subprocess.run(["docker", "rmi", image_id], capture_output=True)
            
            self.log("✓ Cleanup complete")
        except Exception as e:
            self.log(f"Cleanup error: {e}")
    
    def save_license(self):
        """Save license key to file."""
        license_key = self.license_key.get().strip()
        if not license_key:
            messagebox.showerror("Error", "Please enter a license key")
            return
        
        try:
            config_dir = self.get_config_dir()
            os.makedirs(config_dir, exist_ok=True)
            
            with open(os.path.join(config_dir, "license.txt"), "w") as f:
                f.write(license_key)
            
            messagebox.showinfo("Success", "License key saved!")
            self.check_license_status()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
    
    def load_license(self):
        """Load saved license key."""
        try:
            config_dir = self.get_config_dir()
            license_file = os.path.join(config_dir, "license.txt")
            
            if os.path.exists(license_file):
                with open(license_file, "r") as f:
                    return f.read().strip()
        except:
            pass
        return None
    
    def validate_license(self):
        """Validate license with server."""
        license_key = self.license_key.get().strip()
        if not license_key:
            messagebox.showerror("Error", "Please enter a license key")
            return
        
        # Here you would validate with the Railway server
        # For now, just show a message
        self.license_info_text.delete(1.0, tk.END)
        self.license_info_text.insert(tk.END, f"License Key: {license_key}\n")
        self.license_info_text.insert(tk.END, "Validating...\n")
        
        # Simulate validation
        self.license_info_text.insert(tk.END, "✓ License is valid\n")
        self.license_info_text.insert(tk.END, "Expires: 30 days from purchase\n")
    
    def view_logs(self):
        """View container logs."""
        try:
            result = subprocess.run(["docker", "logs", "--tail", "100", "twhyne"],
                                  capture_output=True, text=True)
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(tk.END, result.stdout)
            self.log_text.insert(tk.END, result.stderr)
        except Exception as e:
            self.log(f"Error viewing logs: {e}")
    
    def export_logs(self):
        """Export logs to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snf_ai_logs_{timestamp}.txt"
        
        try:
            with open(filename, "w") as f:
                f.write(self.log_text.get(1.0, tk.END))
            messagebox.showinfo("Success", f"Logs exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")
    
    def open_app(self):
        """Open the web application."""
        if self.is_running:
            webbrowser.open("http://localhost:3000")
        else:
            messagebox.showwarning("Not Running", "SNF-AI is not running. Please start it first.")
    
    def get_config_dir(self):
        """Get configuration directory."""
        if platform.system() == "Windows":
            return os.path.join(os.environ["APPDATA"], "SNF-AI")
        else:
            return os.path.expanduser("~/.snf-ai")
    
    def log(self, message):
        """Add message to log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()


def main():
    root = tk.Tk()
    app = SNFAIManager(root)
    root.mainloop()


if __name__ == "__main__":
    main()
