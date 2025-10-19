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
    CORS(app, origins=["http://localhost:3001", "http://127.0.0.1:3001"])
    
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
