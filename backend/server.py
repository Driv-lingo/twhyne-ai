#!/usr/bin/env python3

import logging
import os
import time
from pathlib import Path
import sys
from typing import Optional, Any
from flask import Flask, request, jsonify
from flask_cors import CORS

# Add the flux_nodes directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'flux_nodes'))

from flux_nodes.base import FluxNode, NodeRegistry
from flux_nodes.language import LanguageNode
from flux_nodes.code import CodeNode
from flux_nodes.math import MathNode
from flux_nodes.planner import PlannerNode
from flux_nodes.vision import VisionNode
from rag_manager import get_rag_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _route_query(prompt: str, node_registry) -> Optional[Any]:
    """Route queries to appropriate nodes based on content analysis with scoring."""
    sys.stderr.write(f"[ROUTING DEBUG] Analyzing query: '{prompt}'\n")
    sys.stderr.flush()
    logger.info(f"[ROUTING] Analyzing query: '{prompt}'")
    prompt_lower = prompt.lower().strip()
    
    # Define scoring for node selection based on keywords
    node_scores = {
        'math-llm-eval': 0,
        'code-codellama-7b': 0,
        'planner-mistral-7b': 0,
        'vision-llava-1.6-7b': 0,
        'language-mistral-7b': 0
    }
    
    # Math indicators - high priority for calculations
    math_indicators = [
        '+', '-', '*', '/', '=', 'calculate', 'compute', 'solve', 'math', 'equation',
        'add', 'subtract', 'multiply', 'divide', 'sum', 'difference', 'product',
        'square', 'root', 'power', 'factorial', 'derivative', 'integral',
        'money', 'dollar', 'billion', 'million', 'thousand', 'cost', 'price', 'buy', 'bought', 'left', 'remain', 'remaining'
    ]
    for indicator in math_indicators:
        if indicator in prompt_lower:
            node_scores['math-llm-eval'] += 2  # High weight for math terms
    
    # Code indicators
    code_keywords = ['code', 'function', 'class', 'method', 'algorithm', 'programming', 'script', 'debug', 'syntax', 'variable', 'loop', 'conditional', 'import', 'library', 'framework']
    for keyword in code_keywords:
        if keyword in prompt_lower:
            node_scores['code-codellama-7b'] += 1
    
    # Planning indicators
    planning_keywords = ['plan', 'schedule', 'organize', 'workflow', 'task', 'project', 'timeline', 'strategy', 'roadmap', 'milestone']
    for keyword in planning_keywords:
        if keyword in prompt_lower:
            node_scores['planner-mistral-7b'] += 1
    
    # Vision indicators
    vision_keywords = ['image', 'picture', 'photo', 'visual', 'see', 'look', 'caption', 'describe', 'analyze']
    for keyword in vision_keywords:
        if keyword in prompt_lower:
            node_scores['vision-llava-1.6-7b'] += 1
    
    # Find the node with the highest score
    best_node_id = max(node_scores, key=node_scores.get)
    if node_scores[best_node_id] > 0:
        print(f"[ROUTING DEBUG] Selected node {best_node_id} with score {node_scores[best_node_id]}")
        node = node_registry.get_node(best_node_id)
        if node and node.is_available:
            logger.info(f"Routing query to {best_node_id} with score {node_scores[best_node_id]}: {prompt}")
            return node
    
    # Default to language node if no strong indicators
    print(f"[ROUTING DEBUG] Defaulting to language node")
    node = node_registry.get_node('language-mistral-7b')
    if node and node.is_available:
        print(f"[ROUTING DEBUG] Selected language-mistral-7b node")
        logger.info(f"Routing general query to language-mistral-7b: {prompt}")
        return node
    
    # Fallback to any available node
    print(f"[ROUTING DEBUG] Fallback to any available node")
    for node_id in node_registry.get_all_node_ids():
        node = node_registry.get_node(node_id)
        if node and node.is_available:
            print(f"[ROUTING DEBUG] Selected fallback node: {node_id}")
            logger.info(f"Routing fallback to {node_id}: {prompt}")
            return node
    
    return None

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization"]}}, supports_credentials=False)
    
    # Initialize node registry
    node_registry = NodeRegistry()
    
    # Get models directory
    models_dir = Path(__file__).parent.parent / 'models'
    
    # Register nodes
    try:
        # Language node
        language_node = LanguageNode(
            node_id='language-mistral-7b',
            name='Language (OpenHermes-Mistral-7B)',
            description='GPU-accelerated language understanding and generation using OpenHermes-2.5-Mistral-7B',
            model_path=models_dir / 'mistral-7b-instruct-q4.gguf'
        )
        node_registry.register_node(language_node)
        logger.info(f"Successfully loaded node: {language_node.name} ({language_node.node_id})")
    except Exception as e:
        logger.error(f"Failed to load language node: {e}")
    
    try:
        # Code node
        code_node = CodeNode(
            node_id='code-codellama-7b',
            name='Code (CodeLlama-7B)',
            description='Code generation and understanding using CodeLlama-7B',
            model_path=models_dir / 'codellama-7b-q4.gguf'
        )
        node_registry.register_node(code_node)
        logger.info(f"Successfully loaded node: {code_node.name} ({code_node.node_id})")
    except Exception as e:
        logger.error(f"Failed to load code node: {e}")
    
    try:
        # Math node
        math_node = MathNode(
            node_id='math-llm-eval',
            name='Math (LLM Eval)',
            description='Solves mathematical problems using a local LLM with a deterministic fallback.',
            model_path=models_dir / 'mistral-7b-instruct-q4.gguf'
        )
        node_registry.register_node(math_node)
        logger.info(f"Successfully loaded node: {math_node.name} ({math_node.node_id})")
    except Exception as e:
        logger.error(f"Failed to load math node: {e}")
    
    try:
        # Planner node
        planner_node = PlannerNode(
            node_id='planner-mistral-7b',
            name='Planner (Mistral-7B)',
            description='Task planning and decomposition using a local instruction-following model',
            model_path=models_dir / 'mistral-7b-instruct-q4.gguf'
        )
        node_registry.register_node(planner_node)
        logger.info(f"Successfully loaded node: {planner_node.name} ({planner_node.node_id})")
    except Exception as e:
        logger.error(f"Failed to load planner node: {e}")
    
    try:
        # Vision node
        vision_node = VisionNode(
            node_id='vision-llava-1.6-7b',
            name='Vision (LLaVA-1.6-7B)',
            description='Image captioning and visual question answering using LLaVA-1.6-7B.',
            model_path=models_dir / 'llava-v1.5-7b-Q4_K.gguf',
            mmproj_path=models_dir / 'mmproj-model-f16.gguf'
        )
        node_registry.register_node(vision_node)
        logger.info(f"Successfully loaded node: {vision_node.name} ({vision_node.node_id})")
    except Exception as e:
        logger.error(f"Failed to load vision node: {e}")
    
    @app.route('/status', methods=['GET', 'OPTIONS'])
    def health_check():
        """Health check endpoint."""
        if request.method == 'OPTIONS':
            logger.info("OPTIONS request received for /status from origin: %s", request.headers.get('Origin', 'Unknown'))
            response = jsonify({'status': 'ok'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
            logger.info("Returning CORS preflight response with status 200")
            return response, 200
        try:
            all_nodes = node_registry.get_all_nodes()
            status = {}
            for node in all_nodes:
                status[node.node_id] = {
                    'name': node.name,
                    'description': node.description,
                    'node_id': node.node_id,
                    'status': node.get_status()
                }
            return jsonify(status)
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/nodes', methods=['GET', 'OPTIONS'])
    def get_nodes():
        """Return all nodes in the format expected by the frontend."""
        if request.method == 'OPTIONS':
            logger.info("OPTIONS request received for /nodes from origin: %s", request.headers.get('Origin', 'Unknown'))
            response = jsonify({'status': 'ok'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
            logger.info("Returning CORS preflight response with status 200")
            return response, 200
        try:
            all_nodes = node_registry.get_all_nodes()
            nodes_list = []
            
            for node in all_nodes:
                # Convert sets to lists for JSON serialization
                capabilities = getattr(node, 'capabilities', [])
                if isinstance(capabilities, set):
                    capabilities = list(capabilities)
                
                keywords = getattr(node, 'keywords', [])
                if isinstance(keywords, set):
                    keywords = list(keywords)
                
                # Get the actual status string, not the full status object
                node_status = node.get_status()
                if isinstance(node_status, dict):
                    status_string = node_status.get('status', 'offline')
                else:
                    status_string = str(node_status)
                
                node_info = {
                    'id': node.node_id,
                    'node_id': node.node_id,
                    'name': node.name,
                    'description': node.description,
                    'status': status_string,
                    'capabilities': capabilities,
                    'keywords': keywords,
                    'is_remote': getattr(node, 'is_remote', False),
                    'version': getattr(node, 'version', '1.0.0'),
                    'memory_requirements': getattr(node, 'memory_requirements', 0),
                    'vram_requirements': getattr(node, 'vram_requirements', None),
                    'metadata': getattr(node, 'metadata', {})
                }
                nodes_list.append(node_info)
            
            return jsonify(nodes_list)
        except Exception as e:
            logger.error(f"Error getting nodes: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/upload', methods=['POST', 'OPTIONS'])
    def upload_file():
        """Handle file uploads for image processing."""
        if request.method == 'OPTIONS':
            logger.info("OPTIONS request received for /upload from origin: %s", request.headers.get('Origin', 'Unknown'))
            response = jsonify({'status': 'ok'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
            logger.info("Returning CORS preflight response with status 200")
            return response, 200
        logger.info(f"Upload request received: {request.content_type}")
        if 'file' not in request.files:
            logger.error("No file part in the request")
            return jsonify({'error': 'No file part in the request. Ensure the file is sent with key "file".'}), 400
        file = request.files['file']
        if file.filename == '':
            logger.error("No selected file")
            return jsonify({'error': 'No selected file. Please choose a file to upload.'}), 400
        if file:
            # Save the file temporarily
            import os
            import uuid
            upload_folder = os.path.join(os.getcwd(), 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            filename = str(uuid.uuid4()) + '_' + file.filename
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)
            logger.info(f"File uploaded: {filepath}")
            return jsonify({'filepath': filepath, 'message': 'File uploaded successfully'})
        logger.error("Upload failed for unknown reason")
        return jsonify({'error': 'Upload failed. Unknown error occurred.'}), 400
    
    @app.route('/query', methods=['POST', 'OPTIONS'])
    def submit_query():
        """Submit a query to the appropriate node."""
        # Flask-CORS handles OPTIONS automatically, just return empty response
        if request.method == 'OPTIONS':
            logger.info("OPTIONS request received for /query from origin: %s", request.headers.get('Origin', 'Unknown'))
            return '', 200
        try:
            data = request.get_json()
            if not data:
                logger.error("No JSON data received")
                return jsonify({'error': 'No JSON data provided'}), 400
            
            prompt = data.get('prompt', '')
            node_id = data.get('node_id')
            conversation_history = data.get('conversation_history', [])
            
            logger.info(f"Received query data: {data}")
            
            if not prompt or not prompt.strip():
                logger.error(f"Empty prompt received: '{prompt}'")
                return jsonify({'error': 'No prompt provided'}), 400
            
            logger.info(f"Processing query: {prompt[:100]}...")
            
            # Route to appropriate node
            if node_id and node_id != 'auto-routed':
                node = node_registry.get_node(node_id)
                if not node or not node.is_available:
                    return jsonify({'error': f'Node {node_id} not available'}), 400
            else:
                node = _route_query(prompt, node_registry)
                if not node:
                    return jsonify({'error': 'No suitable node available'}), 400
            
            # Process query
            from flux_nodes.base import Query, Response
            
            # Check for image path before creating query
            filepath = data.get('filepath', None)
            image_path = data.get('image_path', None)
            parameters = {}
            
            # If vision node and filepath is available, add it to parameters
            if (filepath or image_path) and node.node_id == 'vision-llava-1.6-7b':
                file_to_use = image_path if image_path else filepath
                logger.info(f"Passing filepath {file_to_use} to vision node")
                parameters['image_path'] = file_to_use
            
            query_obj = Query(
                id=f"query_{int(time.time() * 1000)}",
                text=prompt,
                parameters=parameters,
                history=conversation_history
            )
            
            response = node.process(query_obj)
            
            # Only check for completeness if the node is language/planner and response is very short
            # Skip this check for math/code nodes which give precise answers
            if (node.node_id in ['language-mistral-7b', 'planner-mistral-7b'] and 
                response.text and 
                len(response.text) < 50 and 
                not response.text.endswith(('.', '!', '?', '...'))):
                logger.info(f"Short response detected, may need completion for: {prompt[:50]}...")
                follow_up_query = Query(
                    id=f"follow_up_{int(time.time() * 1000)}",
                    text="Please complete the previous answer.",
                    parameters={},
                    history=conversation_history + [{'role': 'assistant', 'content': response.text}]
                )
                follow_up_response = node.process(follow_up_query)
                if follow_up_response.text and follow_up_response.text.strip():
                    response.text += " " + follow_up_response.text
            
            return jsonify({
                'result': response.text,
                'response': response.text,
                'node_id': node.node_id,
                'processing_time': getattr(response, 'processing_time_ms', 0)
            })
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return jsonify({'error': f'Query processing failed: {str(e)}'}), 500
    
    # RAG Management Endpoints
    @app.route('/api/rag/status', methods=['GET'])
    def rag_status():
        """Get RAG system status."""
        try:
            rag_manager = get_rag_manager()
            status = rag_manager.get_status()
            return jsonify(status)
        except Exception as e:
            logger.error(f"Error getting RAG status: {e}")
            return jsonify({'available': False, 'error': str(e)}), 500
    
    @app.route('/api/rag/datasets', methods=['GET'])
    def list_datasets():
        """List all RAG datasets."""
        try:
            rag_manager = get_rag_manager()
            datasets = rag_manager.list_datasets()
            return jsonify({'datasets': datasets})
        except Exception as e:
            logger.error(f"Error listing datasets: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/rag/datasets', methods=['POST'])
    def create_dataset():
        """Create a new RAG dataset."""
        try:
            data = request.get_json()
            name = data.get('name')
            description = data.get('description', '')
            files = data.get('files', [])
            
            if not name or not files:
                return jsonify({'error': 'Name and files are required'}), 400
            
            rag_manager = get_rag_manager()
            dataset = rag_manager.create_dataset(name, description, files)
            
            return jsonify({'success': True, 'dataset': dataset})
        except Exception as e:
            logger.error(f"Error creating dataset: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/rag/datasets/<dataset_id>', methods=['DELETE'])
    def delete_dataset(dataset_id):
        """Delete a RAG dataset."""
        try:
            rag_manager = get_rag_manager()
            success = rag_manager.delete_dataset(dataset_id)
            
            if success:
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Dataset not found'}), 404
        except Exception as e:
            logger.error(f"Error deleting dataset: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/rag/datasets/<dataset_id>/search', methods=['POST'])
    def search_dataset(dataset_id):
        """Search a RAG dataset."""
        try:
            data = request.get_json()
            query = data.get('query', '')
            top_k = data.get('top_k', 5)
            
            if not query:
                return jsonify({'error': 'Query is required'}), 400
            
            rag_manager = get_rag_manager()
            results = rag_manager.search_dataset(dataset_id, query, top_k)
            
            return jsonify({'results': results})
        except Exception as e:
            logger.error(f"Error searching dataset: {e}")
            return jsonify({'error': str(e)}), 500
    
    return app

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Starting Clean SNF-AI Windsurf API Server")
    print("📊 Dashboard available at: http://localhost:5002/dashboard/")
    print("🔧 API endpoint: http://localhost:5002/query")
    print("📝 Status endpoint: http://localhost:5002/status")
    print("=" * 60)
    
    app = create_app()
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=False)
