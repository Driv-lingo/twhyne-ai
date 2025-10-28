#!/usr/bin/env python3
"""
Simple license validation for Docker container.
Checks license on startup and periodically. Exits if invalid.
Includes offline expiry check to prevent air-gap bypass.
"""

import os
import sys
import time
import json
import requests
import threading
from datetime import datetime, timedelta
from pathlib import Path

LICENSE_API = os.environ.get('LICENSE_API_URL', "https://sunny-imagination-production.up.railway.app")
LICENSE_KEY_ENV = "SNF_LICENSE_KEY"
CHECK_INTERVAL_HOURS = 24  # Check daily
CACHE_FILE = Path('/app/.license_cache.json')
MAX_OFFLINE_DAYS = 7  # Allow 7 days offline before forcing reconnection


def save_license_cache(license_key, expiry_date):
    """Save license expiry to local cache."""
    try:
        cache_data = {
            'license_key': license_key,
            'expiry_date': expiry_date,
            'last_validated': datetime.now().isoformat()
        }
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)
    except Exception as e:
        print(f"⚠ Could not save license cache: {e}")


def load_license_cache():
    """Load license cache from disk."""
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠ Could not load license cache: {e}")
    return None


def check_local_expiry(license_key):
    """Check if license has expired based on local cache."""
    cache = load_license_cache()
    
    if not cache:
        return None  # No cache, must validate online
    
    if cache.get('license_key') != license_key:
        return None  # Different license key, must revalidate
    
    # Check if license has expired
    try:
        expiry_date = datetime.fromisoformat(cache['expiry_date'])
        if datetime.now() > expiry_date:
            return False  # License expired locally
        
        # Check if we've been offline too long
        last_validated = datetime.fromisoformat(cache['last_validated'])
        offline_duration = datetime.now() - last_validated
        
        if offline_duration > timedelta(days=MAX_OFFLINE_DAYS):
            print(f"⚠ License not validated online for {offline_duration.days} days")
            return None  # Force online validation
        
        return True  # Valid based on cache
        
    except Exception as e:
        print(f"⚠ Error checking local expiry: {e}")
        return None


def validate_license(license_key):
    """Validate license key with server (with offline fallback)."""
    
    # First, check local expiry
    local_check = check_local_expiry(license_key)
    if local_check is False:
        print("✗ License has expired (local check)")
        return False
    
    # Try online validation
    try:
        response = requests.post(
            f"{LICENSE_API}/api/validate",
            json={"license_key": license_key},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('valid'):
                expiry = data.get('expiry_date', '')
                print(f"✓ License valid until: {expiry}")
                
                # Save to cache for offline use
                save_license_cache(license_key, expiry)
                return True
            else:
                print(f"✗ License invalid: {data.get('message', 'Unknown error')}")
                return False
        else:
            print(f"✗ License server returned status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠ Cannot connect to license server")
        
        # Fallback to cached validation
        if local_check is True:
            cache = load_license_cache()
            last_validated = datetime.fromisoformat(cache['last_validated'])
            offline_days = (datetime.now() - last_validated).days
            print(f"✓ Using cached license (offline for {offline_days} days)")
            print(f"✓ License valid until: {cache['expiry_date']}")
            return True
        else:
            print("✗ No valid license cache available")
            return False
            
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
