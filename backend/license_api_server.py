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


@app.route('/api/admin/licenses', methods=['GET'])
def list_licenses():
    """
    List all licenses with aggregate info (admin endpoint).
    No individual user PII is returned beyond email for license management.
    
    Query params:
        admin_secret: Admin authentication secret
    """
    admin_secret = request.args.get('admin_secret', '')
    if admin_secret != os.environ.get('SNF_ADMIN_SECRET'):
        return jsonify({'error': 'Unauthorized'}), 401

    now = datetime.now()
    license_list = []
    for key, data in LICENSES.items():
        expiry = datetime.fromisoformat(data['expiry_date'])
        license_list.append({
            'license_key': key,
            'email': data.get('email', ''),
            'created_at': data.get('created_at', ''),
            'expiry_date': data['expiry_date'],
            'is_active': data.get('is_active', True),
            'is_expired': expiry < now,
            'device_bound': data.get('device_id') is not None,
            'validation_count': data.get('validation_count', 0),
            'last_validated': data.get('last_validated'),
        })

    return jsonify({
        'total': len(license_list),
        'active': sum(1 for lic in license_list if lic['is_active'] and not lic['is_expired']),
        'expired': sum(1 for lic in license_list if lic['is_expired']),
        'revoked': sum(1 for lic in license_list if not lic['is_active']),
        'licenses': license_list,
    })


@app.route('/api/admin/kpis', methods=['GET'])
def admin_kpi_summary():
    """
    Get aggregate KPI summary across all instances (admin endpoint).
    No individual user data - only aggregate system metrics.
    
    Query params:
        admin_secret: Admin authentication secret
    """
    admin_secret = request.args.get('admin_secret', '')
    if admin_secret != os.environ.get('SNF_ADMIN_SECRET'):
        return jsonify({'error': 'Unauthorized'}), 401

    now = datetime.now()
    total = len(LICENSES)
    active = sum(1 for lic in LICENSES.values()
                 if lic.get('is_active', True) and
                 datetime.fromisoformat(lic['expiry_date']) > now)
    expired = sum(1 for lic in LICENSES.values()
                  if datetime.fromisoformat(lic['expiry_date']) <= now)
    revoked = sum(1 for lic in LICENSES.values()
                  if not lic.get('is_active', True))
    total_validations = sum(lic.get('validation_count', 0) for lic in LICENSES.values())

    # Aggregate instance telemetry
    telemetry_summary = {
        'total_instances_reported': len(TELEMETRY_STORE),
        'aggregate_queries': sum(t.get('total_queries', 0) for t in TELEMETRY_STORE.values()),
        'aggregate_errors': sum(t.get('error_count', 0) for t in TELEMETRY_STORE.values()),
    }

    return jsonify({
        'license_kpis': {
            'total_licenses': total,
            'active_licenses': active,
            'expired_licenses': expired,
            'revoked_licenses': revoked,
            'total_validations': total_validations,
        },
        'telemetry': telemetry_summary,
    })


# Telemetry ingestion - receives anonymous metrics from client instances
TELEMETRY_STORE = {}

@app.route('/api/telemetry/report', methods=['POST'])
def receive_telemetry():
    """
    Receive anonymous aggregate telemetry from client instances.
    No PII or query content is stored.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data'}), 400

        instance_id = data.get('instance_id', 'unknown')
        TELEMETRY_STORE[instance_id] = {
            'total_queries': data.get('total_queries', 0),
            'queries_per_hour': data.get('queries_per_hour', 0),
            'avg_response_time_ms': data.get('avg_response_time_ms', 0),
            'error_rate': data.get('error_rate', 0),
            'error_count': data.get('error_count', 0),
            'uptime_hours': data.get('uptime_hours', 0),
            'version': data.get('version', ''),
            'last_report': datetime.now().isoformat(),
        }

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Telemetry ingestion error: {e}")
        return jsonify({'error': str(e)}), 500


# Update management - serves version manifest to client instances
CURRENT_RELEASE = {
    'latest_version': os.environ.get('LATEST_APP_VERSION', '1.0.0'),
    'release_notes': os.environ.get('RELEASE_NOTES', ''),
    'update_url': os.environ.get('UPDATE_URL', 'https://github.com/Driv-lingo/twhyne-ai/releases/latest'),
}

@app.route('/api/updates/check', methods=['GET'])
def check_for_updates():
    """
    Check if a newer version is available.
    Called by client instances periodically.
    
    Query params:
        current_version: The version the client is running
    """
    current_version = request.args.get('current_version', '0.0.0')

    update_available = False
    try:
        from packaging.version import parse as parse_version
        update_available = parse_version(current_version) < parse_version(CURRENT_RELEASE['latest_version'])
    except ImportError:
        # Fallback: split version strings for comparison
        def _version_tuple(v):
            return tuple(int(x) for x in v.split('.') if x.isdigit())
        try:
            update_available = _version_tuple(current_version) < _version_tuple(CURRENT_RELEASE['latest_version'])
        except (ValueError, TypeError):
            update_available = current_version != CURRENT_RELEASE['latest_version']

    return jsonify({
        'current_version': current_version,
        'latest_version': CURRENT_RELEASE['latest_version'],
        'update_available': update_available,
        'release_notes': CURRENT_RELEASE['release_notes'] if update_available else '',
        'update_url': CURRENT_RELEASE['update_url'] if update_available else '',
    })


@app.route('/api/admin/updates/set', methods=['POST'])
def admin_set_update():
    """
    Set the latest release version and notes (admin endpoint).
    Used to push update notifications to all client instances.
    
    Request:
        {
            "admin_secret": "...",
            "latest_version": "2.0.0",
            "release_notes": "Bug fixes and improvements",
            "update_url": "https://..."
        }
    """
    try:
        data = request.get_json()
        admin_secret = data.get('admin_secret')

        if admin_secret != os.environ.get('SNF_ADMIN_SECRET'):
            return jsonify({'error': 'Unauthorized'}), 401

        if data.get('latest_version'):
            CURRENT_RELEASE['latest_version'] = data['latest_version']
        if data.get('release_notes') is not None:
            CURRENT_RELEASE['release_notes'] = data['release_notes']
        if data.get('update_url'):
            CURRENT_RELEASE['update_url'] = data['update_url']

        logger.info(f"Release updated to v{CURRENT_RELEASE['latest_version']}")

        return jsonify({
            'success': True,
            'release': CURRENT_RELEASE,
        })
    except Exception as e:
        logger.error(f"Update set error: {e}")
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
