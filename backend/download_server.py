#!/usr/bin/env python3
"""
Download server for SNF-AI executable distribution.
Serves the application download after successful registration.
"""

import os
from flask import Flask, send_file, jsonify, request, render_template_string
from flask_cors import CORS
from datetime import datetime
import hashlib

app = Flask(__name__)
CORS(app)

# Download page HTML template
DOWNLOAD_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>SNF-AI Windsurf - Download</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }
        .container {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            font-size: 2.5em;
            margin-bottom: 20px;
        }
        .success-icon {
            font-size: 4em;
            margin: 20px 0;
        }
        .license-info {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }
        .license-key {
            font-family: 'Courier New', monospace;
            font-size: 1.2em;
            background: rgba(0, 0, 0, 0.3);
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
            word-break: break-all;
        }
        .download-btn {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 15px 40px;
            font-size: 1.2em;
            border-radius: 50px;
            cursor: pointer;
            margin: 20px 0;
            transition: all 0.3s;
            text-decoration: none;
            display: inline-block;
        }
        .download-btn:hover {
            background: #45a049;
            transform: scale(1.05);
        }
        .instructions {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 20px;
            margin-top: 30px;
            text-align: left;
        }
        .instructions h3 {
            margin-top: 0;
        }
        .instructions ol {
            margin: 10px 0;
            padding-left: 20px;
        }
        .instructions li {
            margin: 10px 0;
        }
        .system-req {
            background: rgba(255, 165, 0, 0.2);
            border-radius: 10px;
            padding: 15px;
            margin-top: 20px;
        }
        .footer {
            margin-top: 30px;
            font-size: 0.9em;
            opacity: 0.8;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="success-icon">✅</div>
        <h1>Registration Successful!</h1>
        
        <div class="license-info">
            <h3>Your License Key</h3>
            <div class="license-key">{{ license_key }}</div>
            <p>Valid for: 90 days (expires {{ expiry_date }})</p>
            <p>Devices allowed: 3</p>
        </div>
        
        <h2>Download SNF-AI Windsurf</h2>
        <p>Your professional AI system is ready to download.</p>
        
        <a href="/download/app/{{ download_token }}" class="download-btn">
            📥 Download for macOS ({{ file_size }})
        </a>
        
        <div class="instructions">
            <h3>Installation Instructions</h3>
            <ol>
                <li>Download the application using the button above</li>
                <li>Extract the ZIP file</li>
                <li>Run <code>Install.command</code> to install</li>
                <li>Launch SNF-AI Windsurf from Applications</li>
                <li>Enter your license key when prompted</li>
                <li>The app will download AI models (~8GB) on first run</li>
            </ol>
        </div>
        
        <div class="system-req">
            <strong>System Requirements:</strong>
            <ul style="text-align: left;">
                <li>macOS 10.15 or later</li>
                <li>8GB RAM minimum (16GB recommended)</li>
                <li>10GB free disk space (for models)</li>
                <li>Internet connection for activation</li>
            </ul>
        </div>
        
        <div class="footer">
            <p>Keep your license key safe - you'll need it to activate the application.</p>
            <p>Need help? Contact support@twhyne.ai</p>
        </div>
    </div>
</body>
</html>
"""

# Configuration
DOWNLOAD_DIR = os.environ.get('DOWNLOAD_DIR', '/app/downloads')
APP_FILENAME = 'SNF-AI-Windsurf-3.0.0.zip'

@app.route('/download/<license_key>')
def download_page(license_key):
    """Show download page after successful registration."""
    # Validate license key (check with database)
    # For now, we'll assume it's valid if it matches pattern
    if not license_key or len(license_key) < 10:
        return jsonify({'error': 'Invalid license key'}), 404
    
    # Generate download token (expires in 24 hours)
    download_token = hashlib.sha256(f"{license_key}-{datetime.now().date()}".encode()).hexdigest()[:16]
    
    # Calculate expiry date (90 days from now)
    from datetime import timedelta
    expiry_date = (datetime.now() + timedelta(days=90)).strftime('%B %d, %Y')
    
    # Get file size
    file_path = os.path.join(DOWNLOAD_DIR, APP_FILENAME)
    if os.path.exists(file_path):
        file_size = f"{os.path.getsize(file_path) / (1024*1024):.1f} MB"
    else:
        file_size = "~50 MB"
    
    return render_template_string(
        DOWNLOAD_PAGE,
        license_key=license_key,
        expiry_date=expiry_date,
        download_token=download_token,
        file_size=file_size
    )

@app.route('/download/app/<token>')
def download_app(token):
    """Serve the application download."""
    # Validate token (simplified - in production, check against database)
    if not token or len(token) < 10:
        return jsonify({'error': 'Invalid download token'}), 403
    
    file_path = os.path.join(DOWNLOAD_DIR, APP_FILENAME)
    
    if not os.path.exists(file_path):
        # If file doesn't exist, return instructions to upload it
        return jsonify({
            'error': 'Application file not found',
            'instruction': f'Please upload {APP_FILENAME} to {DOWNLOAD_DIR} on the server'
        }), 404
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=APP_FILENAME,
        mimetype='application/zip'
    )

@app.route('/upload', methods=['POST'])
def upload_app():
    """Upload the application file (admin only)."""
    # Check admin token
    admin_token = request.headers.get('X-Admin-Token')
    if admin_token != os.environ.get('ADMIN_TOKEN', 'your-secret-admin-token'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save the file
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, APP_FILENAME)
    file.save(file_path)
    
    return jsonify({
        'success': True,
        'message': f'File uploaded successfully',
        'path': file_path,
        'size': f"{os.path.getsize(file_path) / (1024*1024):.1f} MB"
    })

@app.route('/status')
def status():
    """Check if download server is running and file is available."""
    file_path = os.path.join(DOWNLOAD_DIR, APP_FILENAME)
    file_exists = os.path.exists(file_path)
    
    return jsonify({
        'status': 'running',
        'file_available': file_exists,
        'file_path': file_path if file_exists else None,
        'file_size': f"{os.path.getsize(file_path) / (1024*1024):.1f} MB" if file_exists else None
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5003))
    app.run(host='0.0.0.0', port=port, debug=False)
