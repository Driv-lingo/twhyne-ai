#!/usr/bin/env python3
"""
Enhanced license validation API server for Railway deployment.
Supports registration, validation, and decryption seed generation.
"""

import os
import json
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["https://twhyne.com", "http://localhost:*"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Secret salt for seed generation (CHANGE THIS TO YOUR OWN SECRET)
SECRET_SALT = os.environ.get('SNF_SECRET_SALT', secrets.token_hex(32))

# In-memory license database (in production, use PostgreSQL/MySQL)
# Format: { "license_key": { "email": "", "expiry_date": "", "device_id": "", "created_at": "" } }
LICENSE_DB_FILE = Path('license_database.json')

def load_licenses():
    """Load licenses from file."""
    if LICENSE_DB_FILE.exists():
        try:
            with open(LICENSE_DB_FILE, 'r') as f:
                return json.load(f)
        except:
            logger.error("Failed to load license database")
    return {}

def save_licenses(licenses):
    """Save licenses to file."""
    try:
        with open(LICENSE_DB_FILE, 'w') as f:
            json.dump(licenses, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save license database: {e}")

# Load existing licenses
LICENSES = load_licenses()


def generate_license_key() -> str:
    """Generate a unique license key."""
    return f"SNF-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"


def generate_decryption_seed(license_key: str, device_id: str) -> str:
    """
    Generate deterministic decryption seed for a license.
    This seed is used to derive the model decryption key.
    """
    seed_material = f"{license_key}:{device_id}:{SECRET_SALT}"
    seed = hashlib.sha256(seed_material.encode()).hexdigest()[:32]
    return seed


@app.route('/', methods=['GET'])
def index():
    """Root endpoint."""
    return jsonify({
        'service': 'SNF-AI License Server',
        'version': '2.0.0',
        'endpoints': {
            'register': '/api/registration/register',
            'validate': '/api/registration/validate',
            'status': '/api/status'
        }
    })


@app.route('/api/status', methods=['GET'])
def status():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'total_licenses': len(LICENSES),
        'active_licenses': sum(1 for lic in LICENSES.values() 
                              if datetime.fromisoformat(lic['expiry_date']) > datetime.now())
    })


@app.route('/api/registration/register', methods=['POST', 'OPTIONS'])
def register():
    """
    Register a new user and generate a license key.
    
    Request:
        {
            "email": "user@example.com",
            "duration_days": 90  (optional, default 90)
        }
    
    Response:
        {
            "success": true,
            "license_key": "SNF-XXXXXXXX-XXXXXXXX",
            "email": "user@example.com",
            "expiry_date": "2026-01-25T12:00:00",
            "message": "Registration successful"
        }
    """
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email', '').strip()
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        # Validate email format (basic)
        if '@' not in email:
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Generate license
        license_key = generate_license_key()
        duration_days = data.get('duration_days', 30)  # Default 30 days
        expiry_date = datetime.now() + timedelta(days=duration_days)
        
        # Store license
        LICENSES[license_key] = {
            'email': email,
            'expiry_date': expiry_date.isoformat(),
            'device_id': None,  # Bound on first activation
            'created_at': datetime.now().isoformat(),
            'is_active': True,
            'validation_count': 0,
            'last_validated': None
        }
        
        save_licenses(LICENSES)
        
        logger.info(f"New license generated: {license_key} for {email}")
        
        return jsonify({
            'success': True,
            'license_key': license_key,
            'email': email,
            'expiry_date': expiry_date.isoformat(),
            'duration_days': duration_days,
            'message': f'Registration successful. Your license is valid for {duration_days} days.'
        })
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500


@app.route('/api/registration/validate', methods=['POST', 'OPTIONS'])
def validate():
    """
    Validate a license key and optionally provide decryption seed.
    
    Request:
        {
            "license_key": "SNF-XXXXXXXX-XXXXXXXX",
            "device_id": "abc123def456",
            "request_seed": true  (optional)
        }
    
    Response (valid):
        {
            "valid": true,
            "email": "user@example.com",
            "expiry_date": "2026-01-25T12:00:00",
            "device_id": "abc123def456",
            "decryption_seed": "seed_for_model_decryption",  (if requested)
            "message": "License valid"
        }
    
    Response (invalid):
        {
            "valid": false,
            "message": "License expired/not found/etc"
        }
    """
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'valid': False, 'message': 'No data provided'}), 400
        
        license_key = data.get('license_key', '').strip()
        device_id = data.get('device_id', '').strip()
        request_seed = data.get('request_seed', False)
        
        if not license_key:
            return jsonify({'valid': False, 'message': 'License key required'}), 400
        
        if not device_id:
            return jsonify({'valid': False, 'message': 'Device ID required'}), 400
        
        # Check if license exists
        if license_key not in LICENSES:
            logger.warning(f"Unknown license key: {license_key}")
            return jsonify({'valid': False, 'message': 'Invalid license key'}), 401
        
        license_data = LICENSES[license_key]
        
        # Check if active
        if not license_data.get('is_active', True):
            logger.warning(f"Revoked license: {license_key}")
            return jsonify({'valid': False, 'message': 'License has been revoked'}), 401
        
        # Check expiry
        expiry_date = datetime.fromisoformat(license_data['expiry_date'])
        if expiry_date < datetime.now():
            logger.warning(f"Expired license: {license_key}")
            return jsonify({'valid': False, 'message': 'License expired'}), 401
        
        # Device binding check
        bound_device = license_data.get('device_id')
        
        if bound_device is None:
            # First activation - bind to this device
            license_data['device_id'] = device_id
            logger.info(f"License {license_key} bound to device {device_id}")
            save_licenses(LICENSES)
        
        elif bound_device != device_id:
            # Trying to use on different device
            logger.warning(f"Device mismatch for {license_key}: {device_id} != {bound_device}")
            return jsonify({
                'valid': False,
                'message': 'License already in use on another device'
            }), 403
        
        # Update validation stats
        license_data['validation_count'] = license_data.get('validation_count', 0) + 1
        license_data['last_validated'] = datetime.now().isoformat()
        save_licenses(LICENSES)
        
        # Build response
        response = {
            'valid': True,
            'email': license_data['email'],
            'expiry_date': license_data['expiry_date'],
            'device_id': device_id,
            'message': 'License valid'
        }
        
        # Add decryption seed if requested
        if request_seed:
            seed = generate_decryption_seed(license_key, device_id)
            response['decryption_seed'] = seed
            logger.info(f"Decryption seed provided for {license_key}")
        
        logger.info(f"License validated: {license_key} (validation #{license_data['validation_count']})")
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return jsonify({'valid': False, 'message': f'Validation failed: {str(e)}'}), 500


@app.route('/api/admin/revoke', methods=['POST'])
def revoke_license():
    """
    Revoke a license (admin endpoint - should be protected in production).
    
    Request:
        {
            "license_key": "SNF-XXXXXXXX-XXXXXXXX",
            "admin_secret": "your-admin-secret"
        }
    """
    try:
        data = request.get_json()
        admin_secret = data.get('admin_secret')
        
        # Simple admin auth (use proper auth in production)
        if admin_secret != os.environ.get('SNF_ADMIN_SECRET'):
            return jsonify({'error': 'Unauthorized'}), 401
        
        license_key = data.get('license_key')
        
        if license_key not in LICENSES:
            return jsonify({'error': 'License not found'}), 404
        
        LICENSES[license_key]['is_active'] = False
        save_licenses(LICENSES)
        
        logger.info(f"License revoked: {license_key}")
        
        return jsonify({'success': True, 'message': 'License revoked'})
        
    except Exception as e:
        logger.error(f"Revoke error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/extend', methods=['POST'])
def extend_license():
    """
    Extend license expiration (admin endpoint).
    
    Request:
        {
            "license_key": "SNF-XXXXXXXX-XXXXXXXX",
            "additional_days": 30,
            "admin_secret": "your-admin-secret"
        }
    """
    try:
        data = request.get_json()
        admin_secret = data.get('admin_secret')
        
        if admin_secret != os.environ.get('SNF_ADMIN_SECRET'):
            return jsonify({'error': 'Unauthorized'}), 401
        
        license_key = data.get('license_key')
        additional_days = data.get('additional_days', 30)
        
        if license_key not in LICENSES:
            return jsonify({'error': 'License not found'}), 404
        
        current_expiry = datetime.fromisoformat(LICENSES[license_key]['expiry_date'])
        new_expiry = current_expiry + timedelta(days=additional_days)
        
        LICENSES[license_key]['expiry_date'] = new_expiry.isoformat()
        save_licenses(LICENSES)
        
        logger.info(f"License extended: {license_key} by {additional_days} days")
        
        return jsonify({
            'success': True,
            'new_expiry': new_expiry.isoformat(),
            'message': f'License extended by {additional_days} days'
        })
        
    except Exception as e:
        logger.error(f"Extend error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5003))
    
    print("=" * 60)
    print("SNF-AI License Server")
    print("=" * 60)
    print(f"Port: {port}")
    print(f"Secret Salt: {'SET' if SECRET_SALT else 'NOT SET (using default)'}")
    print(f"Admin Secret: {'SET' if os.environ.get('SNF_ADMIN_SECRET') else 'NOT SET'}")
    print(f"Licenses: {len(LICENSES)} loaded")
    print("=" * 60)
    print("")
    
    app.run(host='0.0.0.0', port=port, debug=False)
