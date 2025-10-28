#!/usr/bin/env python3
"""
Simple license management website.
Users can register, purchase licenses, and manage their subscriptions.
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import json
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
CORS(app)

# Database file (simple JSON for now - use real DB for production)
DB_FILE = Path('license_db.json')

def load_db():
    """Load database."""
    if DB_FILE.exists():
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {'users': {}, 'licenses': {}}

def save_db(db):
    """Save database."""
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=2)

def generate_license_key():
    """Generate unique license key."""
    return f"SNF-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"

def hash_password(password):
    """Hash password."""
    return hashlib.sha256(password.encode()).hexdigest()


# Web Pages

@app.route('/')
def index():
    """Home page."""
    return render_template('index.html')

@app.route('/register')
def register_page():
    """Registration page."""
    return render_template('register.html')

@app.route('/login')
def login_page():
    """Login page."""
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """User dashboard."""
    if 'user_email' not in session:
        return redirect(url_for('login_page'))
    
    db = load_db()
    user_email = session['user_email']
    
    # Get user's licenses
    user_licenses = {k: v for k, v in db['licenses'].items() 
                    if v.get('email') == user_email}
    
    return render_template('dashboard.html', 
                         email=user_email, 
                         licenses=user_licenses)


# API Endpoints

@app.route('/api/register', methods=['POST'])
def api_register():
    """Register new user."""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    db = load_db()
    
    # Check if user exists
    if email in db['users']:
        return jsonify({'error': 'Email already registered'}), 400
    
    # Create user
    db['users'][email] = {
        'email': email,
        'password_hash': hash_password(password),
        'created_at': datetime.now().isoformat()
    }
    
    save_db(db)
    
    return jsonify({
        'success': True,
        'message': 'Registration successful. Please log in.'
    })

@app.route('/api/login', methods=['POST'])
def api_login():
    """Login user."""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    db = load_db()
    user = db['users'].get(email)
    
    if not user or user['password_hash'] != hash_password(password):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    session['user_email'] = email
    
    return jsonify({
        'success': True,
        'message': 'Login successful',
        'redirect': '/dashboard'
    })

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Logout user."""
    session.clear()
    return jsonify({'success': True})

@app.route('/api/purchase-license', methods=['POST'])
def api_purchase_license():
    """Purchase a new 30-day license."""
    if 'user_email' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    # In production, integrate with Stripe/PayPal here
    # For now, just generate the license (manual payment)
    
    email = session['user_email']
    license_key = generate_license_key()
    
    db = load_db()
    db['licenses'][license_key] = {
        'email': email,
        'license_key': license_key,
        'created_at': datetime.now().isoformat(),
        'expiry_date': (datetime.now() + timedelta(days=30)).isoformat(),
        'is_active': True,
        'payment_status': 'manual'  # Change to 'paid' with real payment
    }
    
    save_db(db)
    
    return jsonify({
        'success': True,
        'license_key': license_key,
        'expiry_date': db['licenses'][license_key]['expiry_date'],
        'message': '30-day license generated successfully'
    })

@app.route('/api/validate', methods=['POST'])
def api_validate():
    """Validate license (for Docker containers)."""
    data = request.get_json()
    license_key = data.get('license_key', '').strip()
    
    if not license_key:
        return jsonify({'valid': False, 'message': 'License key required'}), 400
    
    db = load_db()
    license_data = db['licenses'].get(license_key)
    
    if not license_data:
        return jsonify({'valid': False, 'message': 'Invalid license key'}), 404
    
    # Check if active
    if not license_data.get('is_active', False):
        return jsonify({'valid': False, 'message': 'License revoked'}), 401
    
    # Check expiry
    expiry_date = datetime.fromisoformat(license_data['expiry_date'])
    if expiry_date < datetime.now():
        return jsonify({'valid': False, 'message': 'License expired'}), 401
    
    return jsonify({
        'valid': True,
        'email': license_data['email'],
        'expiry_date': license_data['expiry_date'],
        'message': 'License valid'
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
