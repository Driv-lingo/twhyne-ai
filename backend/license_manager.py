#!/usr/bin/env python3
"""
License management system for SNF-AI.
Handles license key validation and activation.
"""

import os
import sys
import json
import hashlib
import requests
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from pathlib import Path
import platform
import uuid

# Registration API URL (your Railway deployment)
REGISTRATION_API = "https://web-production-d31c0.up.railway.app"

class LicenseManager:
    """Manages license validation and storage."""
    
    def __init__(self):
        self.license_file = self._get_license_path()
        self.device_id = self._get_device_id()
        
    def _get_license_path(self):
        """Get the path to store license data."""
        if getattr(sys, 'frozen', False):
            # Running as executable
            app_dir = os.path.dirname(sys.executable)
        else:
            # Running as script
            app_dir = os.path.dirname(os.path.abspath(__file__))
            
        license_dir = os.path.join(app_dir, '.snf_ai_data')
        os.makedirs(license_dir, exist_ok=True)
        return os.path.join(license_dir, 'license.json')
        
    def _get_device_id(self):
        """Generate a unique device ID."""
        mac = uuid.getnode()
        hostname = platform.node()
        system = platform.system()
        
        device_string = f"{mac}-{hostname}-{system}"
        return hashlib.sha256(device_string.encode()).hexdigest()[:16]
        
    def load_license(self):
        """Load existing license from file."""
        if os.path.exists(self.license_file):
            try:
                with open(self.license_file, 'r') as f:
                    return json.load(f)
            except:
                return None
        return None
        
    def save_license(self, license_data):
        """Save license data to file."""
        with open(self.license_file, 'w') as f:
            json.dump(license_data, f, indent=2)
            
    def validate_license(self, license_key):
        """Validate license key with the registration API."""
        try:
            response = requests.post(
                f"{REGISTRATION_API}/api/registration/validate",
                json={
                    "license_key": license_key,
                    "device_id": self.device_id
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('valid'):
                    # Save license data
                    license_data = {
                        'license_key': license_key,
                        'email': data.get('email'),
                        'expiry_date': data.get('expiry_date'),
                        'device_id': self.device_id,
                        'validated_at': datetime.now().isoformat()
                    }
                    self.save_license(license_data)
                    return True, "License activated successfully!"
                else:
                    return False, data.get('message', 'Invalid license key')
            else:
                return False, "Failed to validate license"
                
        except requests.exceptions.RequestException as e:
            # Offline validation fallback
            return self._offline_validate(license_key)
        except Exception as e:
            return False, f"Error: {str(e)}"
            
    def _offline_validate(self, license_key):
        """Offline license validation (basic check)."""
        # Check if we have a cached valid license
        existing = self.load_license()
        if existing and existing.get('license_key') == license_key:
            # Check expiry
            expiry = existing.get('expiry_date')
            if expiry:
                expiry_date = datetime.fromisoformat(expiry)
                if expiry_date > datetime.now():
                    return True, "License validated (offline mode)"
                else:
                    return False, "License expired"
            return True, "License validated (offline mode)"
        return False, "Cannot validate license offline"
        
    def check_license(self):
        """Check if a valid license exists."""
        license_data = self.load_license()
        if not license_data:
            return False, None
            
        # Check expiry
        expiry = license_data.get('expiry_date')
        if expiry:
            expiry_date = datetime.fromisoformat(expiry)
            if expiry_date < datetime.now():
                return False, "License expired"
                
        return True, license_data


class LicenseActivationGUI:
    """GUI for license activation."""
    
    def __init__(self, license_manager):
        self.license_manager = license_manager
        self.root = tk.Tk()
        self.root.title("SNF-AI License Activation")
        self.root.geometry("500x400")
        self.root.resizable(False, False)
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.root.winfo_screenheight() // 2) - (400 // 2)
        self.root.geometry(f'+{x}+{y}')
        
        self.license_activated = False
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface."""
        # Logo/Title
        title_frame = tk.Frame(self.root, bg="#2196F3", height=80)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title = tk.Label(
            title_frame,
            text="SNF-AI Windsurf",
            font=("Arial", 24, "bold"),
            bg="#2196F3",
            fg="white"
        )
        title.pack(expand=True)
        
        # Main content
        content_frame = tk.Frame(self.root, padx=40, pady=30)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Instructions
        instructions = tk.Label(
            content_frame,
            text="Please enter your license key to activate SNF-AI:",
            font=("Arial", 12),
            wraplength=400
        )
        instructions.pack(pady=(0, 20))
        
        # License key input
        tk.Label(content_frame, text="License Key:", font=("Arial", 10)).pack(anchor=tk.W)
        
        self.license_entry = tk.Entry(
            content_frame,
            font=("Courier", 12),
            width=40
        )
        self.license_entry.pack(pady=(5, 20))
        self.license_entry.bind('<Return>', lambda e: self.activate_license())
        
        # Buttons
        button_frame = tk.Frame(content_frame)
        button_frame.pack(pady=10)
        
        self.activate_btn = tk.Button(
            button_frame,
            text="Activate",
            command=self.activate_license,
            bg="#4CAF50",
            fg="white",
            padx=30,
            pady=10,
            font=("Arial", 12, "bold")
        )
        self.activate_btn.pack(side=tk.LEFT, padx=5)
        
        self.register_btn = tk.Button(
            button_frame,
            text="Get License",
            command=self.open_registration,
            bg="#2196F3",
            fg="white",
            padx=20,
            pady=10,
            font=("Arial", 12)
        )
        self.register_btn.pack(side=tk.LEFT, padx=5)
        
        # No trial mode - license required
        
        # Status label
        self.status_label = tk.Label(
            content_frame,
            text="",
            font=("Arial", 10),
            fg="gray"
        )
        self.status_label.pack(pady=10)
        
        # Footer
        footer = tk.Label(
            content_frame,
            text="© 2025 Twhyne AI. All rights reserved.",
            font=("Arial", 9),
            fg="gray"
        )
        footer.pack(side=tk.BOTTOM, pady=10)
        
    def activate_license(self):
        """Activate the entered license key."""
        license_key = self.license_entry.get().strip()
        
        if not license_key:
            messagebox.showwarning("Invalid Input", "Please enter a license key")
            return
            
        # Disable button during validation
        self.activate_btn.config(state=tk.DISABLED, text="Validating...")
        self.status_label.config(text="Validating license...", fg="blue")
        self.root.update()
        
        # Validate license
        valid, message = self.license_manager.validate_license(license_key)
        
        if valid:
            self.status_label.config(text=message, fg="green")
            self.license_activated = True
            messagebox.showinfo("Success", message)
            self.root.destroy()
        else:
            self.status_label.config(text=message, fg="red")
            self.activate_btn.config(state=tk.NORMAL, text="Activate")
            messagebox.showerror("Activation Failed", message)
            
    def open_registration(self):
        """Open registration page in browser."""
        import webbrowser
        registration_url = f"{REGISTRATION_API}/register"
        webbrowser.open(registration_url)
        self.status_label.config(
            text="Opening registration page in browser...",
            fg="blue"
        )
        
    # Trial mode removed - license required for access
            
    def run(self):
        """Run the GUI and return activation status."""
        self.root.mainloop()
        return self.license_activated


def check_and_activate_license():
    """Check for valid license or prompt for activation."""
    manager = LicenseManager()
    
    # Check existing license
    valid, license_data = manager.check_license()
    
    if valid:
        print("✓ License validated")
        # Check expiry
        expiry = license_data.get('expiry_date')
        if expiry:
            expiry_date = datetime.fromisoformat(expiry)
            days_left = (expiry_date - datetime.now()).days
            if days_left > 0:
                print(f"  License expires in {days_left} days")
            elif days_left == 0:
                print("  License expires today")
            else:
                print("  License expired - renewal required")
                valid = False
        
        if valid:
            return True  # License is valid
    
    # Show activation GUI - license required
    print("License activation required...")
    gui = LicenseActivationGUI(manager)
    activated = gui.run()
    
    return activated  # True if activated, False if not


if __name__ == '__main__':
    # Test the license system
    activated = check_and_activate_license()
    
    if activated:
        print("Application running with valid license")
    else:
        print("Application not activated - license required")
        sys.exit(1)
