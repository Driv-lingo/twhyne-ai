#!/usr/bin/env python3
"""
Simplified test server for CI environment.
This version doesn't load heavy model files and provides basic endpoints for testing.
"""

import logging
from flask import Flask, jsonify
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
                .container {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 40px; max-width: 600px; text-align: center; }}
                .license-key {{ font-family: monospace; background: rgba(0,0,0,0.3); padding: 10px; border-radius: 5px; margin: 20px 0; }}
                .download-btn {{ background: #4CAF50; color: white; border: none; padding: 15px 40px; font-size: 1.2em; border-radius: 50px; cursor: pointer; text-decoration: none; display: inline-block; margin: 20px 0; }}
                .download-btn:hover {{ background: #45a049; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>✅ Registration Successful!</h1>
                <p>Your License Key:</p>
                <div class="license-key">{license_key}</div>
                <p>Valid for 90 days</p>
                <h2>Download Instructions</h2>
                <p>The SNF-AI Windsurf executable is available at:</p>
                <a href="https://github.com/Driv-lingo/twhyne-ai/releases/latest" class="download-btn">📥 Download from GitHub</a>
                <ol style="text-align: left;">
                    <li>Click the download button above</li>
                    <li>Download SNF-AI-Windsurf-3.0.0.zip</li>
                    <li>Extract and run Install.command</li>
                    <li>Enter your license key when prompted</li>
                </ol>
                <p style="margin-top: 30px; font-size: 0.9em;">Keep your license key safe!</p>
            </div>
        </body>
        </html>
        """
        return html
    
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
