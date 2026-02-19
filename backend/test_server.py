#!/usr/bin/env python3
"""
Simplified test server for CI and local demo environments.
This version doesn't load heavy model files and provides mock endpoints
that match the real server's API so the frontend can connect.
"""

import logging
import time
from flask import Flask, jsonify, request
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Track start time for uptime calculation
_start_time = time.time()

# Mock node definitions matching the real server's node registry
MOCK_NODES = [
    {
        'id': 'language-mistral-7b',
        'node_id': 'language-mistral-7b',
        'name': 'Language (Mistral-7B)',
        'description': 'General language understanding and generation (demo mode)',
        'status': 'online',
        'capabilities': ['text-generation', 'question-answering', 'summarization'],
        'keywords': ['language', 'text', 'general'],
        'is_remote': False,
        'version': '1.0.0',
    },
    {
        'id': 'code-codellama-7b',
        'node_id': 'code-codellama-7b',
        'name': 'Code (CodeLlama-7B)',
        'description': 'Code generation and understanding (demo mode)',
        'status': 'online',
        'capabilities': ['code-generation', 'code-analysis'],
        'keywords': ['code', 'programming', 'function'],
        'is_remote': False,
        'version': '1.0.0',
    },
    {
        'id': 'math-llm-eval',
        'node_id': 'math-llm-eval',
        'name': 'Math (LLM Eval)',
        'description': 'Mathematical problem solving (demo mode)',
        'status': 'online',
        'capabilities': ['math', 'calculation'],
        'keywords': ['math', 'calculate', 'solve'],
        'is_remote': False,
        'version': '1.0.0',
    },
    {
        'id': 'planner-mistral-7b',
        'node_id': 'planner-mistral-7b',
        'name': 'Planner (Mistral-7B)',
        'description': 'Task planning and decomposition (demo mode)',
        'status': 'online',
        'capabilities': ['planning', 'task-decomposition'],
        'keywords': ['plan', 'schedule', 'organize'],
        'is_remote': False,
        'version': '1.0.0',
    },
    {
        'id': 'vision-llava-1.6-7b',
        'node_id': 'vision-llava-1.6-7b',
        'name': 'Vision (LLaVA-1.6-7B)',
        'description': 'Image captioning and visual QA (demo mode)',
        'status': 'online',
        'capabilities': ['image-captioning', 'visual-qa'],
        'keywords': ['image', 'picture', 'visual'],
        'is_remote': False,
        'version': '1.0.0',
    },
]

# Demo responses by node type
DEMO_RESPONSES = {
    'language-mistral-7b': "This is a demo response from the Language node. In production, this would use a Mistral-7B model for natural language understanding and generation.",
    'code-codellama-7b': "```python\n# Demo response from Code node\ndef hello():\n    return 'In production, CodeLlama-7B generates real code'\n\nhello()\n```",
    'math-llm-eval': "Demo: The answer is 42. In production, the Math node uses LLM evaluation with deterministic fallback for accurate calculations.",
    'planner-mistral-7b': "Demo Plan:\n1. Step 1: Analyze the task\n2. Step 2: Break it into subtasks\n3. Step 3: Execute each subtask\n\nIn production, the Planner node creates detailed task plans.",
    'vision-llava-1.6-7b': "Demo: [Image analysis would appear here]. In production, LLaVA-1.6-7B analyzes images and answers visual questions.",
}


def create_test_app():
    """Create a simplified Flask app for testing and local demo."""
    app = Flask(__name__)
    # NOTE: Allow all origins for local demo/development use only.
    # The production server.py uses more restrictive CORS settings.
    CORS(app, resources={r"/*": {"origins": "*"}})
    
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
        """Get available nodes in the format expected by the frontend."""
        return jsonify(MOCK_NODES)
    
    @app.route('/query', methods=['POST'])
    def query():
        """Query endpoint that returns demo responses."""
        data = request.get_json() or {}
        prompt = data.get('prompt', '')
        node_id = data.get('node_id', 'language-mistral-7b')

        # Simple keyword routing if auto-routed
        if not node_id or node_id == 'auto-routed':
            prompt_lower = prompt.lower()
            if any(w in prompt_lower for w in ['code', 'function', 'class', 'programming']):
                node_id = 'code-codellama-7b'
            elif any(w in prompt_lower for w in ['calculate', 'math', 'solve', '+', '-', '*', '/']):
                node_id = 'math-llm-eval'
            elif any(w in prompt_lower for w in ['plan', 'schedule', 'organize', 'task']):
                node_id = 'planner-mistral-7b'
            elif any(w in prompt_lower for w in ['image', 'picture', 'photo', 'visual']):
                node_id = 'vision-llava-1.6-7b'
            else:
                node_id = 'language-mistral-7b'

        response_text = DEMO_RESPONSES.get(node_id, DEMO_RESPONSES['language-mistral-7b'])

        return jsonify({
            'result': response_text,
            'response': response_text,
            'node_id': node_id,
            'node_used': node_id,
            'processing_time': 0,
            'status': 'success'
        })
    
    @app.route('/upload', methods=['POST'])
    def upload():
        """Handle file uploads (mock)."""
        return jsonify({'filepath': '/tmp/mock_upload.jpg', 'message': 'File uploaded (demo mode)'})

    @app.route('/feedback', methods=['POST'])
    def feedback():
        """Handle feedback submissions."""
        return jsonify({'status': 'ok', 'message': 'Feedback received (demo mode)'})

    @app.route('/api/rag/status', methods=['GET'])
    def rag_status():
        """RAG system status."""
        return jsonify({'available': False, 'message': 'RAG not available in demo mode'})

    @app.route('/api/rag/datasets', methods=['GET'])
    def rag_datasets():
        """List RAG datasets."""
        return jsonify({'datasets': []})

    @app.route('/api/telemetry/kpis', methods=['GET'])
    def telemetry_kpis():
        """Public KPI endpoint."""
        uptime_s = int(time.time() - _start_time)
        return jsonify({
            'uptime': f'{uptime_s // 3600}h {(uptime_s % 3600) // 60}m',
            'version': '1.0.0',
            'node_availability': {n['node_id']: {'available': True} for n in MOCK_NODES},
        })

    @app.route('/api/license/status', methods=['GET'])
    def license_status():
        """License status endpoint."""
        return jsonify({'licensed': False, 'message': 'Demo mode - no license required'})

    @app.route('/api/updates/check', methods=['GET'])
    def updates_check():
        """Update check endpoint."""
        return jsonify({
            'current_version': '1.0.0',
            'latest_version': '1.0.0',
            'update_available': False,
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
    

    return app

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5002))
    
    print("=" * 60)
    print("🧪 Starting SNF-AI Windsurf (Demo Mode)")
    print(f"📝 Status endpoint: http://localhost:{port}/status")
    print(f"🔧 API endpoint: http://localhost:{port}/query")
    print(f"📊 Nodes endpoint: http://localhost:{port}/nodes")
    print("=" * 60)
    
    app = create_test_app()
    app.run(host='0.0.0.0', port=port, debug=False)
