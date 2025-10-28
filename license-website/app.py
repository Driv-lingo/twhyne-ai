#!/usr/bin/env python3
"""
Simple license management website.
Users can register, purchase licenses, and manage their subscriptions.
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_cors import CORS
import json
import hashlib
import secrets
import uuid
import stripe
from datetime import datetime, timedelta
from pathlib import Path
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
CORS(app)

# Stripe configuration
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PRICE_ID = os.environ.get('STRIPE_PRICE_ID', '')  # Create this in Stripe Dashboard
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
LICENSE_PRICE = 20  # $20/month

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
    """Create Stripe checkout session for license purchase."""
    if 'user_email' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    email = session['user_email']
    
    # Check if Stripe is configured
    if not stripe.api_key or not STRIPE_PRICE_ID:
        # Fallback to manual license generation (for testing)
        license_key = generate_license_key()
        db = load_db()
        db['licenses'][license_key] = {
            'email': email,
            'license_key': license_key,
            'created_at': datetime.now().isoformat(),
            'expiry_date': (datetime.now() + timedelta(days=30)).isoformat(),
            'is_active': True,
            'payment_status': 'manual'
        }
        save_db(db)
        
        return jsonify({
            'success': True,
            'license_key': license_key,
            'expiry_date': db['licenses'][license_key]['expiry_date'],
            'message': '30-day license generated (test mode)'
        })
    
    # Create Stripe checkout session
    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=email,
            payment_method_types=['card'],
            line_items=[{
                'price': STRIPE_PRICE_ID,
                'quantity': 1,
            }],
            mode='payment',
            allow_promotion_codes=True,
            success_url=request.host_url + 'dashboard?payment=success',
            cancel_url=request.host_url + 'dashboard?payment=cancel',
            metadata={
                'user_email': email,
                'product': 'snf_ai_license_30days'
            }
        )
        
        return jsonify({
            'success': True,
            'checkout_url': checkout_session.url
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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


@app.route('/download/windows')
def download_windows():
    """Serve Windows installation package."""
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    # Create ZIP file with scripts
    import zipfile
    import io
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add scripts
        zip_file.writestr('START-SNF-AI.bat', get_windows_start_script())
        zip_file.writestr('STOP-SNF-AI.bat', get_windows_stop_script())
        zip_file.writestr('UPDATE-SNF-AI.bat', get_windows_update_script())
        zip_file.writestr('README.txt', get_readme())
    
    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='SNF-AI-Windows.zip'
    )

@app.route('/download/mac')
def download_mac():
    """Serve Mac installation package."""
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    # Create ZIP file with scripts
    import zipfile
    import io
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add scripts
        zip_file.writestr('START-SNF-AI.command', get_mac_start_script())
        zip_file.writestr('STOP-SNF-AI.command', get_mac_stop_script())
        zip_file.writestr('UPDATE-SNF-AI.command', get_mac_update_script())
        zip_file.writestr('README.txt', get_readme())
    
    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='SNF-AI-Mac.zip'
    )

@app.route('/api/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events."""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle successful payment
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        email = session['metadata']['user_email']
        
        # Generate license
        license_key = generate_license_key()
        db = load_db()
        db['licenses'][license_key] = {
            'email': email,
            'license_key': license_key,
            'created_at': datetime.now().isoformat(),
            'expiry_date': (datetime.now() + timedelta(days=30)).isoformat(),
            'is_active': True,
            'payment_status': 'paid',
            'stripe_session_id': session['id']
        }
        save_db(db)
        
        # TODO: Send email to customer with license key
        print(f"License generated for {email}: {license_key}")
    
    return jsonify({'success': True})


# Script content functions
def get_windows_start_script():
    return '''@echo off
cls
color 0A
title SNF-AI Windsurf

echo ============================================
echo         SNF-AI WINDSURF STARTER
echo ============================================
echo.

:: Check if Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo ERROR: Docker is not running!
    echo.
    echo Please start Docker Desktop first, then run this again.
    echo.
    pause
    exit /b 1
)

:: Check for license file
set LICENSE_FILE=%USERPROFILE%\.snf-ai-license
if exist "%LICENSE_FILE%" (
    set /p LICENSE_KEY=<"%LICENSE_FILE%"
    echo License found
) else (
    echo First time setup - Enter your license key
    echo.
    set /p LICENSE_KEY=License key (SNF-XXXXXXXX-XXXXXXXX): 
    
    if "%LICENSE_KEY%"=="" (
        color 0C
        echo ERROR: No license key entered
        pause
        exit /b 1
    )
    
    echo %LICENSE_KEY%> "%LICENSE_FILE%"
    echo License saved for future use
)

echo.
echo Starting SNF-AI...
echo.

docker stop twhyne >nul 2>&1
docker rm twhyne >nul 2>&1

echo Checking for updates...
docker pull twhyne/twhyne:licensed >nul 2>&1 || echo Using cached version

echo Starting application...
docker run -d ^
  --name twhyne ^
  -e SNF_LICENSE_KEY=%LICENSE_KEY% ^
  -p 3000:3000 ^
  -p 5001:5001 ^
  --mount source=snf_models,target=/app/models ^
  --mount source=snf_logs,target=/app/logs ^
  --mount source=snf_data,target=/app/data ^
  --mount source=snf_uploads,target=/app/uploads ^
  --mount source=snf_rag,target=/app/rag_storage ^
  --mount source=snf_conversations,target=/app/conversations ^
  --restart unless-stopped ^
  twhyne/twhyne:licensed >nul 2>&1

if %ERRORLEVEL% EQU 0 (
    color 0A
    echo.
    echo SUCCESS: SNF-AI is running!
    echo.
    echo Opening in browser...
    timeout /t 3 /nobreak >nul
    start http://localhost:3000
    
    docker image prune -f >nul 2>&1
    
    echo.
    echo ============================================
    echo   Access at: http://localhost:3000
    echo   To stop: Run STOP-SNF-AI.bat
    echo ============================================
) else (
    color 0C
    echo.
    echo ERROR: Failed to start
    echo Check that Docker is running and try again
)

echo.
pause
'''

def get_windows_stop_script():
    return '''@echo off
echo Stopping SNF-AI...
docker stop twhyne
if %ERRORLEVEL% EQU 0 (
    echo SNF-AI stopped successfully
) else (
    echo SNF-AI was not running
)
pause
'''

def get_windows_update_script():
    return '''@echo off
echo ============================================
echo         SNF-AI UPDATE TOOL
echo ============================================
echo.

set LICENSE_FILE=%USERPROFILE%\.snf-ai-license
if not exist "%LICENSE_FILE%" (
    echo ERROR: No license found. Run START-SNF-AI.bat first
    pause
    exit /b 1
)

set /p LICENSE_KEY=<"%LICENSE_FILE%"

echo Downloading latest version...
docker pull twhyne/twhyne:latest

echo.
echo Stopping current version...
docker stop twhyne >nul 2>&1
docker rm twhyne >nul 2>&1

echo Starting updated version...
docker run -d ^
  --name twhyne ^
  -e SNF_LICENSE_KEY=%LICENSE_KEY% ^
  -p 3000:3000 ^
  -p 5001:5001 ^
  --mount source=snf_models,target=/app/models ^
  --mount source=snf_logs,target=/app/logs ^
  --mount source=snf_data,target=/app/data ^
  --mount source=snf_uploads,target=/app/uploads ^
  --mount source=snf_rag,target=/app/rag_storage ^
  --mount source=snf_conversations,target=/app/conversations ^
  --restart unless-stopped ^
  twhyne/twhyne:latest >nul 2>&1

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: Updated to latest version!
    echo.
    
    docker image prune -f >nul 2>&1
    
    echo Your data has been preserved.
    echo.
    echo Opening in browser...
    start http://localhost:3000
) else (
    echo.
    echo ERROR: Update failed
)

pause
'''

def get_mac_start_script():
    return '''#!/bin/bash
clear
echo "╔══════════════════════════════════════════╗"
echo "║        SNF-AI WINDSURF STARTER          ║"
echo "╚══════════════════════════════════════════╝"
echo ""

if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo ""
    echo "Please start Docker Desktop first, then run this again."
    echo ""
    echo "Press Enter to exit..."
    read
    exit 1
fi

LICENSE_FILE="$HOME/.snf-ai-license"
if [ -f "$LICENSE_FILE" ]; then
    LICENSE_KEY=$(cat "$LICENSE_FILE")
    echo "✓ License found"
else
    echo "📝 First time setup - Enter your license key"
    echo ""
    read -p "License key (SNF-XXXXXXXX-XXXXXXXX): " LICENSE_KEY
    
    if [ -z "$LICENSE_KEY" ]; then
        echo "❌ No license key entered"
        echo "Press Enter to exit..."
        read
        exit 1
    fi
    
    echo "$LICENSE_KEY" > "$LICENSE_FILE"
    echo "✓ License saved for future use"
fi

echo ""
echo "🚀 Starting SNF-AI..."
echo ""

docker stop twhyne 2>/dev/null && echo "Stopped old instance"
docker rm twhyne 2>/dev/null

echo "Checking for updates..."
docker pull twhyne/twhyne:licensed 2>/dev/null || echo "Using cached version"

echo "Starting application..."
docker run -d \\
  --name twhyne \\
  -e SNF_LICENSE_KEY="$LICENSE_KEY" \\
  -p 3000:3000 \\
  -p 5001:5001 \\
  --mount source=snf_models,target=/app/models \\
  --mount source=snf_logs,target=/app/logs \\
  --mount source=snf_data,target=/app/data \\
  --mount source=snf_uploads,target=/app/uploads \\
  --mount source=snf_rag,target=/app/rag_storage \\
  --mount source=snf_conversations,target=/app/conversations \\
  --restart unless-stopped \\
  twhyne/twhyne:licensed > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SNF-AI is running!"
    echo ""
    echo "Opening in browser..."
    sleep 3
    open http://localhost:3000
    
    docker image prune -f > /dev/null 2>&1
    
    echo ""
    echo "════════════════════════════════════════"
    echo "  Access at: http://localhost:3000"
    echo "  To stop: Run STOP-SNF-AI"
    echo "════════════════════════════════════════"
else
    echo ""
    echo "❌ Failed to start"
    echo "Check that Docker is running and try again"
fi

echo ""
echo "Press Enter to close this window..."
read
'''

def get_mac_stop_script():
    return '''#!/bin/bash
echo "Stopping SNF-AI..."
docker stop twhyne
if [ $? -eq 0 ]; then
    echo "SNF-AI stopped successfully"
else
    echo "SNF-AI was not running"
fi
echo "Press Enter to close..."
read
'''

def get_mac_update_script():
    return '''#!/bin/bash
echo "============================================"
echo "         SNF-AI UPDATE TOOL"
echo "============================================"
echo ""

LICENSE_FILE="$HOME/.snf-ai-license"
if [ ! -f "$LICENSE_FILE" ]; then
    echo "ERROR: No license found. Run START-SNF-AI first"
    echo "Press Enter to exit..."
    read
    exit 1
fi

LICENSE_KEY=$(cat "$LICENSE_FILE")

echo "Downloading latest version..."
docker pull twhyne/twhyne:latest

echo ""
echo "Stopping current version..."
docker stop twhyne 2>/dev/null
docker rm twhyne 2>/dev/null

echo "Starting updated version..."
docker run -d \\
  --name twhyne \\
  -e SNF_LICENSE_KEY="$LICENSE_KEY" \\
  -p 3000:3000 \\
  -p 5001:5001 \\
  --mount source=snf_models,target=/app/models \\
  --mount source=snf_logs,target=/app/logs \\
  --mount source=snf_data,target=/app/data \\
  --mount source=snf_uploads,target=/app/uploads \\
  --mount source=snf_rag,target=/app/rag_storage \\
  --mount source=snf_conversations,target=/app/conversations \\
  --restart unless-stopped \\
  twhyne/twhyne:latest > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Updated to latest version!"
    echo ""
    
    docker image prune -f > /dev/null 2>&1
    
    echo "Your data has been preserved."
    echo ""
    echo "Opening in browser..."
    open http://localhost:3000
else
    echo ""
    echo "❌ Update failed"
fi

echo ""
echo "Press Enter to close..."
read
'''

def get_readme():
    return '''SNF-AI WINDSURF - INSTALLATION
===============================

STEP 1: INSTALL DOCKER
----------------------
Download Docker Desktop from: https://docker.com
Install it and restart your computer.

STEP 2: START SNF-AI
--------------------
Windows: Double-click START-SNF-AI.bat
Mac: Double-click START-SNF-AI.command

First time: It will ask for your license key
After that: It remembers your license

STEP 3: USE SNF-AI
------------------
Your browser will open automatically
Or go to: http://localhost:3000

TO STOP:
--------
Windows: Double-click STOP-SNF-AI.bat
Mac: Double-click STOP-SNF-AI.command

TO UPDATE:
----------
Windows: Double-click UPDATE-SNF-AI.bat
Mac: Double-click UPDATE-SNF-AI.command
(Your data is preserved during updates)

THAT'S IT!
----------
No command line needed.
No technical knowledge required.
Just double-click to start/stop/update.

Support: support@twhyne.com
'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
