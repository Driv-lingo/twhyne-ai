#!/usr/bin/env python3
"""
Simple license validation for Docker container.
Checks license on startup and periodically. Exits if invalid.
"""

import os
import sys
import time
import requests
import threading
from datetime import datetime

LICENSE_API = "https://web-production-d31c0.up.railway.app"
LICENSE_KEY_ENV = "SNF_LICENSE_KEY"
CHECK_INTERVAL_HOURS = 24  # Check daily


def validate_license(license_key):
    """Validate license key with server."""
    try:
        response = requests.post(
            f"{LICENSE_API}/api/registration/validate",
            json={"license_key": license_key},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('valid'):
                expiry = data.get('expiry_date', '')
                print(f"✓ License valid until: {expiry}")
                return True
            else:
                print(f"✗ License invalid: {data.get('message', 'Unknown error')}")
                return False
        else:
            print(f"✗ License server returned status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠ Cannot connect to license server - allowing startup (grace period)")
        return True  # Allow if server is down (grace period)
    except Exception as e:
        print(f"✗ License validation error: {e}")
        return False


def check_license_loop(license_key):
    """Periodically check license. Exit if invalid."""
    while True:
        time.sleep(CHECK_INTERVAL_HOURS * 3600)
        print(f"\n[{datetime.now()}] Running periodic license check...")
        
        if not validate_license(license_key):
            print("\n" + "="*60)
            print("LICENSE EXPIRED OR INVALID")
            print("="*60)
            print("Please renew your license to continue using SNF-AI")
            print("Contact: support@twhyne.com")
            print("="*60)
            os._exit(1)  # Force exit


def main():
    """Main license check on startup."""
    print("\n" + "="*60)
    print("SNF-AI Windsurf - License Check")
    print("="*60)
    
    # Get license key
    license_key = os.environ.get(LICENSE_KEY_ENV)
    
    if not license_key:
        print("\n✗ ERROR: License key not provided")
        print(f"\nPlease set the {LICENSE_KEY_ENV} environment variable:")
        print(f"  docker run -e {LICENSE_KEY_ENV}=your-key-here ...")
        print("\nGet a license at: https://twhyne.com/register")
        print("="*60)
        sys.exit(1)
    
    # Validate license
    print(f"\nValidating license key: {license_key[:12]}...")
    
    if not validate_license(license_key):
        print("\n✗ LICENSE VALIDATION FAILED")
        print("\nPossible reasons:")
        print("  - License key is invalid")
        print("  - License has expired (30-day limit)")
        print("  - License server is unreachable")
        print("\nPlease check your license or contact support")
        print("="*60)
        sys.exit(1)
    
    print("\n✓ License validation successful!")
    print("="*60)
    
    # Start background license checker
    checker_thread = threading.Thread(
        target=check_license_loop,
        args=(license_key,),
        daemon=True
    )
    checker_thread.start()
    print(f"✓ Periodic license check enabled (every {CHECK_INTERVAL_HOURS}h)")


if __name__ == '__main__':
    main()
