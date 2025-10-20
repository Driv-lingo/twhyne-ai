#!/usr/bin/env python3
"""
Simplified test server for CI environment.
This version doesn't load heavy model files and provides basic endpoints for testing.
"""

import logging
from flask import Flask, jsonify, request
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_app():
    """Create a simplified Flask app for testing."""
    app = Flask(__name__)
    CORS(app, origins=["http://localhost:3001", "http://127.0.0.1:3001", "https://twhyne.com"])
    
    @app.route('/status', methods=['GET'])
    def status():
        """Health check endpoint."""
        return jsonify({
            'status': 'healthy',
            'message': 'Test server is running',
            'environment': 'ci_test'
        })
    
    @app.route('/nodes', methods=['GET'])
    def get_nodes():
        """Get available nodes (mock for testing)."""
        return jsonify({
            'nodes': [
                {'id': 'test', 'name': 'Test Node', 'status': 'active'}
            ]
        })
    
    @app.route('/query', methods=['POST'])
    def query():
        """Simple query endpoint for testing."""
        return jsonify({
            'response': 'Test response from CI server',
            'node_used': 'test',
            'status': 'success'
        })
    
    @app.route('/download/<license_key>')
    def download_page(license_key):
        """Show download page after registration."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Download SNF-AI Windsurf</title>
            <style>
                body {{ font-family: -apple-system, sans-serif; background: linear-gradient(135deg, #667eea, #764ba2); color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
                .container {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 40px; max-width: 700px; text-align: center; }}
                .license-key {{ font-family: monospace; background: rgba(0,0,0,0.3); padding: 10px; border-radius: 5px; margin: 20px 0; }}
                .download-options {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 30px 0; }}
                .download-btn {{ background: #4CAF50; color: white; border: none; padding: 15px 20px; font-size: 1.1em; border-radius: 10px; cursor: pointer; text-decoration: none; display: block; transition: all 0.3s ease; }}
                .download-btn:hover {{ background: #45a049; transform: translateY(-2px); }}
                .download-btn .platform {{ font-size: 1.3em; margin-bottom: 5px; }}
                .download-btn .size {{ font-size: 0.9em; opacity: 0.8; }}
                .instructions {{ text-align: left; background: rgba(0,0,0,0.2); padding: 20px; border-radius: 10px; margin: 20px 0; }}
                .instructions h3 {{ margin-top: 0; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>✅ Registration Successful!</h1>
                <p>Your License Key:</p>
                <div class="license-key">{license_key}</div>
                <p>Valid for 90 days</p>
                
                <h2>Choose Your Platform</h2>
                <div class="download-options">
                    <a href="https://github.com/Driv-lingo/twhyne-ai/releases/download/v3.0.0/SNF-AI-Windsurf-Windows.zip" class="download-btn">
                        <div class="platform">🪟 Windows</div>
                        <div class="size">35.8 MB</div>
                    </a>
                    <a href="https://github.com/Driv-lingo/twhyne-ai/releases/latest" class="download-btn">
                        <div class="platform">🍎 Mac (Intel)</div>
                        <div class="size">94 MB</div>
                    </a>
                    <a href="https://github.com/Driv-lingo/twhyne-ai/releases/latest" class="download-btn">
                        <div class="platform">🍎 Mac (M1/M2/M3)</div>
                        <div class="size">89 MB</div>
                    </a>
                </div>
                
                <div class="instructions">
                    <h3>📋 Installation Instructions</h3>
                    <p><strong>Windows:</strong></p>
                    <ol>
                        <li>Download and extract the Windows ZIP file</li>
                        <li>Double-click <code>SNF-AI-Windsurf.exe</code> to start</li>
                        <li>Click "Run anyway" if Windows Defender shows a warning</li>
                        <li>Your browser will open automatically</li>
                        <li>Enter your license key when prompted</li>
                    </ol>
                    
                    <p><strong>Mac:</strong></p>
                    <ol>
                        <li>Download the appropriate Mac version for your processor</li>
                        <li>Extract and run <code>Install.command</code></li>
                        <li>Or drag the app to your Applications folder</li>
                        <li>Enter your license key when prompted</li>
                    </ol>
                </div>
                
                <p style="margin-top: 30px; font-size: 0.9em;">
                    💡 <strong>First Run:</strong> The app will download AI models (~8GB) automatically<br>
                    🔒 <strong>Keep your license key safe!</strong> Valid for 90 days on up to 3 devices
                </p>
            </div>
        </body>
        </html>
        """
        return html
    
    @app.route('/api/registration/register', methods=['POST'])
    def register_user():
        """Handle user registration and return a license key."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            email = data.get('email', '')
            if not email:
                return jsonify({'error': 'Email is required'}), 400
            
            # Generate a simple license key (in production, this would be more secure)
            import uuid
            license_key = f"SNF-{uuid.uuid4().hex[:8].upper()}"
            
            # In a real system, store this in a database
            logger.info(f"Registered user with email: {email}, license key: {license_key}")
            
            return jsonify({
                'success': True,
                'license_key': license_key,
                'message': 'Registration successful. Your license key is valid for 90 days.'
            })
        except Exception as e:
            logger.error(f"Error in registration: {e}")
            return jsonify({'error': f'Registration failed: {str(e)}'}), 500
    
    # Add CORS configuration for all endpoints
    @app.after_request
    def add_cors_headers(response):
        """Add CORS headers to every response, ensuring no duplicates."""
        response.headers.pop('Access-Control-Allow-Origin', None)  # Remove any existing header
        response.headers.add('Access-Control-Allow-Origin', 'https://twhyne.com')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        return response
    
    # Handle OPTIONS requests explicitly for all endpoints
    @app.route('/api/registration/register', methods=['OPTIONS'])
    def register_options():
        """Handle CORS preflight for registration endpoint."""
        response = jsonify({'status': 'ok'})
        response.headers.pop('Access-Control-Allow-Origin', None)  # Remove any existing header
        response.headers.add('Access-Control-Allow-Origin', 'https://twhyne.com')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        return response, 200
    
    @app.route('/api/registration/validate', methods=['OPTIONS'])
    def validate_options():
        """Handle CORS preflight for validation endpoint."""
        response = jsonify({'status': 'ok'})
        response.headers.pop('Access-Control-Allow-Origin', None)  # Remove any existing header
        response.headers.add('Access-Control-Allow-Origin', 'https://twhyne.com')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        return response, 200
    
    @app.route('/api/registration/renew', methods=['OPTIONS'])
    def renew_options():
        """Handle CORS preflight for renewal endpoint."""
        response = jsonify({'status': 'ok'})
        response.headers.pop('Access-Control-Allow-Origin', None)  # Remove any existing header
        response.headers.add('Access-Control-Allow-Origin', 'https://twhyne.com')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        return response, 200
    
    return app

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5002))
    
    print("=" * 60)
    print("🧪 Starting Test SNF-AI Server for CI")
    print(f"📝 Status endpoint: http://localhost:{port}/status")
    print(f"🔧 API endpoint: http://localhost:{port}/query")
    print("=" * 60)
    
    app = create_test_app()
    app.run(host='0.0.0.0', port=port, debug=False)
