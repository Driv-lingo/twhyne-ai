#!/usr/bin/env python3
"""Generate a test license for Docker testing."""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

def generate_license_key():
    return f"SNF-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"

# Create test license
license_key = generate_license_key()
license_data = {
    'email': 'docker-test@example.com',
    'license_key': license_key,
    'created_at': datetime.now().isoformat(),
    'expiry_date': (datetime.now() + timedelta(days=30)).isoformat(),
    'is_active': True,
    'payment_status': 'test'
}

print(f"License Key: {license_key}")
print(f"Expires: {license_data['expiry_date']}")
print(f"\nTest with:")
print(f"export SNF_LICENSE_KEY='{license_key}'")
print(f"\nAdd this to Railway license_db.json:")
print(json.dumps({license_key: license_data}, indent=2))
