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
    logger.info(f"[ROUTING] Analyzing query: '{prompt}'")
    prompt_lower = prompt.lower().strip()

    node_scores = {
        'math-llm-eval': 0,
        'code-codellama-7b': 0,
        'planner-mistral-7b': 0,
        'vision-llava-1.6-7b': 0,
        'language-mistral-7b': 0
    }

    math_indicators = [
        '+', '-', '*', '/', '=', 'calculate', 'compute', 'solve', 'math', 'equation',
        'add', 'subtract', 'multiply', 'divide', 'sum', 'difference', 'product',
        'square', 'root', 'power', 'factorial', 'derivative', 'integral',
        'money', 'dollar', 'billion', 'million', 'thousand', 'cost', 'price', 'buy', 'bought', 'left', 'remain', 'remaining'
    ]
    for indicator in math_indicators:
        if indicator in prompt_lower:
            node_scores['math-llm-eval'] += 2

    code_keywords = ['code', 'function', 'class', 'method', 'algorithm', 'programming', 'script', 'debug', 'syntax', 'variable', 'loop', 'conditional', 'import', 'library', 'framework']
    for keyword in code_keywords:
        if keyword in prompt_lower:
            node_scores['code-codellama-7b'] += 1

    planning_keywords = ['plan', 'schedule', 'organize', 'workflow', 'task', 'project', 'timeline', 'strategy', 'roadmap', 'milestone']
    for keyword in planning_keywords:
        if keyword in prompt_lower:
            node_scores['planner-mistral-7b'] += 1

    vision_keywords = ['image', 'picture', 'photo', 'visual', 'see', 'look', 'caption', 'describe', 'analyze']
    for keyword in vision_keywords:
        if keyword in prompt_lower:
            node_scores['vision-llava-1.6-7b'] += 1

    # Find the node with the highest score that is actually registered/available
    best_node_id = max(node_scores, key=node_scores.get)
    if node_scores[best_node_id] > 0:
        node = node_registry.get_node(best_node_id)
        if node and node.is_available:
            logger.info(f"Routing query to {best_node_id} with score {node_scores[best_node_id]}")
            return node

    # Default to language node
    node = node_registry.get_node('language-mistral-7b')
    if node and node.is_available:
        logger.info("Routing general query to language-mistral-7b")
        return node

    # Fallback to any available node
    for node_id in node_registry.get_all_node_ids():
        node = node_registry.get_node(node_id)
        if node and node.is_available:
            logger.info(f"Routing fallback to {node_id}")
            return node

    return None

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization"]}}, supports_credentials=False)

    node_registry = NodeRegistry()
    models_dir = Path(__file__).parent.parent / 'models'

    # Always register the language node (single ~4GB model, handles general queries).
    try:
        language_node = LanguageNode(
            node_id='language-mistral-7b',
            name='Language (OpenHermes-Mistral-7B)',
            description='Language understanding and generation using Mistral-7B',
            model_path=models_dir / 'mistral-7b-instruct-q4.gguf'
        )
        node_registry.register_node(language_node)
        logger.info(f"Registered node: {language_node.name} ({language_node.node_id})")
    except Exception as e:
        logger.error(f"Failed to register language node: {e}")

    # The additional expert nodes each load their own multi-GB model. On a
    # typical CPU-only machine (8-16GB RAM) loading all of them at once will
    # exhaust memory, so they are opt-in via TWHYNE_ALL_NODES=1.
    if os.environ.get("TWHYNE_ALL_NODES") == "1":
        for factory in (
            lambda: CodeNode(node_id='code-codellama-7b', name='Code (CodeLlama-7B)',
                             description='Code generation using CodeLlama-7B',
                             model_path=models_dir / 'codellama-7b-q4.gguf'),
            lambda: MathNode(node_id='math-llm-eval', name='Math (LLM Eval)',
                             description='Solves mathematical problems using a local LLM.',
                             model_path=models_dir / 'mistral-7b-instruct-q4.gguf'),
            lambda: PlannerNode(node_id='planner-mistral-7b', name='Planner (Mistral-7B)',
                                description='Task planning and decomposition',
                                model_path=models_dir / 'mistral-7b-instruct-q4.gguf'),
            lambda: VisionNode(node_id='vision-llava-1.6-7b', name='Vision (LLaVA-1.6-7B)',
                               description='Image captioning and visual QA using LLaVA.',
                               model_path=models_dir / 'llava-v1.5-7b-Q4_K.gguf',
                               mmproj_path=models_dir / 'mmproj-model-f16.gguf'),
        ):
            try:
                n = factory()
                node_registry.register_node(n)
                logger.info(f"Registered node: {n.name} ({n.node_id})")
            except Exception as e:
                logger.error(f"Failed to register optional node: {e}")

    @app.route('/status', methods=['GET', 'OPTIONS'])
    def health_check():
        if request.method == 'OPTIONS':
            return jsonify({'status': 'ok'}), 200
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
        if request.method == 'OPTIONS':
            return jsonify({'status': 'ok'}), 200
        try:
            all_nodes = node_registry.get_all_nodes()
            nodes_list = []
            for node in all_nodes:
                capabilities = getattr(node, 'capabilities', [])
                if isinstance(capabilities, set):
                    capabilities = list(capabilities)
                keywords = getattr(node, 'keywords', [])
                if isinstance(keywords, set):
                    keywords = list(keywords)
                node_status = node.get_status()
                if isinstance(node_status, dict):
                    status_string = node_status.get('status', 'offline')
                else:
                    status_string = str(node_status)
                nodes_list.append({
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
                })
            return jsonify(nodes_list)
        except Exception as e:
            logger.error(f"Error getting nodes: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/upload', methods=['POST', 'OPTIONS'])
    def upload_file():
        if request.method == 'OPTIONS':
            return jsonify({'status': 'ok'}), 200
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request.'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file.'}), 400
        import uuid
        upload_folder = os.path.join(os.getcwd(), 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        filename = str(uuid.uuid4()) + '_' + file.filename
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        return jsonify({'filepath': filepath, 'message': 'File uploaded successfully'})

    @app.route('/query', methods=['POST', 'OPTIONS'])
    def submit_query():
        if request.method == 'OPTIONS':
            return '', 200
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400

            prompt = data.get('prompt', '')
            node_id = data.get('node_id')
            conversation_history = data.get('conversation_history', [])

            if len(conversation_history) > 10:
                conversation_history = conversation_history[-5:]

            if not prompt or not prompt.strip():
                return jsonify({'error': 'No prompt provided'}), 400

            logger.info(f"Processing query: {prompt[:100]}...")

            if node_id and node_id != 'auto-routed':
                node = node_registry.get_node(node_id)
                if not node or not node.is_available:
                    node = _route_query(prompt, node_registry)
            else:
                node = _route_query(prompt, node_registry)
            if not node:
                return jsonify({'error': 'No suitable node available'}), 400

            from flux_nodes.base import Query

            filepath = data.get('filepath', None)
            image_path = data.get('image_path', None)
            parameters = {}
            if (filepath or image_path) and node.node_id == 'vision-llava-1.6-7b':
                parameters['image_path'] = image_path if image_path else filepath

            query_obj = Query(
                id=f"query_{int(time.time() * 1000)}",
                text=prompt,
                parameters=parameters,
                history=conversation_history
            )

            response = node.process(query_obj)

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
        try:
            return jsonify(get_rag_manager().get_status())
        except Exception as e:
            return jsonify({'available': False, 'error': str(e)}), 500

    @app.route('/api/rag/datasets', methods=['GET'])
    def list_datasets():
        try:
            return jsonify({'datasets': get_rag_manager().list_datasets()})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/rag/datasets', methods=['POST'])
    def create_dataset():
        try:
            data = request.get_json()
            name = data.get('name')
            files = data.get('files', [])
            if not name or not files:
                return jsonify({'error': 'Name and files are required'}), 400
            dataset = get_rag_manager().create_dataset(name, data.get('description', ''), files)
            return jsonify({'success': True, 'dataset': dataset})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/rag/datasets/<dataset_id>', methods=['DELETE'])
    def delete_dataset(dataset_id):
        try:
            if get_rag_manager().delete_dataset(dataset_id):
                return jsonify({'success': True})
            return jsonify({'error': 'Dataset not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/rag/datasets/<dataset_id>/search', methods=['POST'])
    def search_dataset(dataset_id):
        try:
            data = request.get_json()
            query = data.get('query', '')
            if not query:
                return jsonify({'error': 'Query is required'}), 400
            results = get_rag_manager().search_dataset(dataset_id, query, data.get('top_k', 5))
            return jsonify({'results': results})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return app

if __name__ == '__main__':
    print("=" * 60)
    print("Starting Twhyne AI backend on :5002")
    print("=" * 60)
    app = create_app()
    app.run(host='0.0.0.0', port=5002, debug=False)
