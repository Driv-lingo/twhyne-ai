#!/usr/bin/env python3

import logging
import os
import threading
import time
from pathlib import Path
import sys
from typing import Optional, Any
from flask import Flask, request, jsonify
from flask_cors import CORS

sys.path.append(os.path.join(os.path.dirname(__file__), 'flux_nodes'))

from flux_nodes.base import FluxNode, NodeRegistry
from flux_nodes.language import LanguageNode
from flux_nodes.code import CodeNode
from flux_nodes.math import MathNode
from flux_nodes.planner import PlannerNode
from flux_nodes.vision import VisionNode
from rag_manager import get_rag_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# llama.cpp is NOT thread-safe: two requests generating on the same model at
# once segfault the process. All inference goes through this lock so queries
# queue up instead of crashing the server.
_INFER_LOCK = threading.Lock()

# Cosine-similarity score above which retrieved sources ground the answer.
GROUND_THRESHOLD = 0.30
# Max characters of retrieved context to inject. PDF-extracted text tokenizes
# densely (~1 token per char in bad stretches), so this must leave real
# headroom inside the 8192-token window for the question and the answer.
MAX_CONTEXT_CHARS = 6500


def _route_query(prompt: str, node_registry) -> Optional[Any]:
    logger.info(f"[ROUTING] Analyzing query: '{prompt}'")
    p = prompt.lower().strip()
    scores = {'math-llm-eval': 0, 'code-codellama-7b': 0, 'planner-mistral-7b': 0,
              'vision-llava-1.6-7b': 0, 'language-mistral-7b': 0}

    for ind in ['+', '-', '*', '/', '=', 'calculate', 'compute', 'solve', 'math', 'equation',
                'add', 'subtract', 'multiply', 'divide', 'sum', 'product', 'square', 'root',
                'derivative', 'integral', 'integrate', 'differentiate']:
        if ind in p:
            scores['math-llm-eval'] += 2
    for kw in ['code', 'function', 'class', 'method', 'algorithm', 'programming', 'script',
               'debug', 'syntax', 'variable', 'loop', 'python', 'javascript']:
        if kw in p:
            scores['code-codellama-7b'] += 1
    for kw in ['plan', 'schedule', 'organize', 'workflow', 'itinerary', 'trip', 'project', 'timeline', 'roadmap']:
        if kw in p:
            scores['planner-mistral-7b'] += 1
    for kw in ['image', 'picture', 'photo', 'visual', 'diagram', 'screenshot']:
        if kw in p:
            scores['vision-llava-1.6-7b'] += 1

    best = max(scores, key=scores.get)
    if scores[best] > 0:
        node = node_registry.get_node(best)
        if node and node.is_available:
            logger.info(f"Routing to {best} (score {scores[best]})")
            return node
    node = node_registry.get_node('language-mistral-7b')
    if node and node.is_available:
        return node
    for nid in node_registry.get_all_node_ids():
        node = node_registry.get_node(nid)
        if node and node.is_available:
            return node
    return None


def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization"]}}, supports_credentials=False)

    node_registry = NodeRegistry()
    models_dir = Path(__file__).parent.parent / 'models'

    node_specs = [
        lambda: LanguageNode(node_id='language-mistral-7b', name='Language (OpenHermes-Mistral-7B)',
                             description='Language understanding and generation using Mistral-7B',
                             model_path=models_dir / 'mistral-7b-instruct-q4.gguf'),
        lambda: MathNode(node_id='math-llm-eval', name='Math (SymPy Symbolic)',
                         description='Exact arithmetic, algebra and calculus using SymPy.',
                         model_path=models_dir / 'mistral-7b-instruct-q4.gguf'),
        lambda: PlannerNode(node_id='planner-mistral-7b', name='Planner (Mistral-7B)',
                            description='Task planning and decomposition',
                            model_path=models_dir / 'mistral-7b-instruct-q4.gguf'),
        lambda: CodeNode(node_id='code-codellama-7b', name='Code (CodeLlama-7B)',
                         description='Code generation using CodeLlama-7B',
                         model_path=models_dir / 'codellama-7b-q4.gguf'),
        lambda: VisionNode(node_id='vision-llava-1.6-7b', name='Vision (LLaVA-1.6-7B)',
                           description='Image captioning and visual QA using LLaVA.',
                           model_path=models_dir / 'llava-v1.5-7b-Q4_K.gguf',
                           mmproj_path=models_dir / 'mmproj-model-f16.gguf'),
    ]
    for spec in node_specs:
        try:
            n = spec()
            node_registry.register_node(n)
            logger.info(f"Registered node: {n.name} ({n.node_id})")
        except Exception as e:
            logger.error(f"Failed to register a node: {e}")

    @app.route('/status', methods=['GET', 'OPTIONS'])
    def health_check():
        if request.method == 'OPTIONS':
            return jsonify({'status': 'ok'}), 200
        try:
            status = {}
            for node in node_registry.get_all_nodes():
                status[node.node_id] = {'name': node.name, 'description': node.description,
                                        'node_id': node.node_id, 'status': node.get_status()}
            return jsonify(status)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/nodes', methods=['GET', 'OPTIONS'])
    def get_nodes():
        if request.method == 'OPTIONS':
            return jsonify({'status': 'ok'}), 200
        try:
            nodes_list = []
            for node in node_registry.get_all_nodes():
                caps = getattr(node, 'capabilities', [])
                if isinstance(caps, set):
                    caps = list(caps)
                kws = getattr(node, 'keywords', [])
                if isinstance(kws, set):
                    kws = list(kws)
                ns = node.get_status()
                status_string = ns.get('status', 'online') if isinstance(ns, dict) else str(ns)
                nodes_list.append({
                    'id': node.node_id, 'node_id': node.node_id, 'name': node.name,
                    'description': node.description, 'status': status_string,
                    'capabilities': caps, 'keywords': kws,
                    'is_remote': getattr(node, 'is_remote', False),
                    'version': getattr(node, 'version', '1.0.0'),
                    'metadata': getattr(node, 'metadata', {}),
                })
            return jsonify(nodes_list)
        except Exception as e:
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
        filepath = os.path.join(upload_folder, str(uuid.uuid4()) + '_' + file.filename)
        file.save(filepath)
        return jsonify({'filepath': filepath, 'message': 'File uploaded successfully'})

    def _retrieve(prompt, dataset_id):
        """Semantic retrieval. Returns (context, sources, top_score).

        Context is capped at MAX_CONTEXT_CHARS so the grounded prompt always
        fits inside the model's context window.
        """
        rm = get_rag_manager()
        datasets = rm.list_datasets()
        if not dataset_id and datasets:
            dataset_id = datasets[0]['id']
        if not dataset_id:
            return "", [], 0.0
        results = rm.search_dataset(dataset_id, prompt, top_k=8)
        if not results:
            return "", [], 0.0
        top_score = results[0]['score']
        kept = [r for r in results if r['score'] >= max(0.2, top_score - 0.15)]
        context, sources = "", []
        for r in kept:
            piece = f"[Source: {r['source']}]\n{r['content']}\n\n"
            if len(context) + len(piece) > MAX_CONTEXT_CHARS:
                # Add a truncated remainder to stay within budget, then stop.
                remaining = MAX_CONTEXT_CHARS - len(context)
                if remaining > 200:
                    context += piece[:remaining]
                    if r['source'] not in sources:
                        sources.append(r['source'])
                break
            context += piece
            if r['source'] not in sources:
                sources.append(r['source'])
        return context, sources, top_score

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

            from flux_nodes.base import Query

            # ---- RETRIEVAL-FIRST ROUTING ---------------------------------
            dataset_id = data.get('dataset_id')
            forced = bool(data.get('use_rag')) or bool(dataset_id)
            context, sources, top_score = _retrieve(prompt, dataset_id)
            should_ground = forced or (bool(context) and top_score >= GROUND_THRESHOLD)

            if forced and not context:
                msg = "I don't have that in my provided sources."
                return jsonify({'result': msg, 'response': msg,
                                'node_id': 'language-mistral-7b', 'sources': []})

            if should_ground and context:
                logger.info(f"Grounded answer (top_score={top_score}). Sources: {sources}")
                lang = node_registry.get_node('language-mistral-7b')
                grounded = (
                    "You are a careful assistant. Answer the question using ONLY the "
                    "information in the sources below, and cite the source name(s). "
                    "If the answer is not fully contained in the sources, say what IS "
                    "supported and note the rest is not in the provided sources. "
                    "Do not add facts that are not in the sources.\n\n"
                    f"Sources:\n{context}\nQuestion: {prompt}\n\nAnswer:"
                )
                # No conversation history in grounded mode - keeps the prompt
                # small and prevents earlier long answers from leaking in.
                q = Query(id=f"query_{int(time.time() * 1000)}", text=grounded,
                          parameters={}, history=[])
                with _INFER_LOCK:
                    response = lang.process(q)
                text = response.text
                if sources:
                    text += "\n\n---\nSources: " + ", ".join(sources)
                return jsonify({'result': text, 'response': text,
                                'node_id': 'language-mistral-7b', 'sources': sources,
                                'grounded': True, 'top_score': top_score})

            # ---- Specialist routing (ungrounded) -------------------------
            logger.info(f"Processing query: {prompt[:100]}...")
            if node_id and node_id != 'auto-routed':
                node = node_registry.get_node(node_id)
                if not node or not node.is_available:
                    node = _route_query(prompt, node_registry)
            else:
                node = _route_query(prompt, node_registry)
            if not node:
                return jsonify({'error': 'No suitable node available'}), 400

            filepath = data.get('filepath', None)
            image_path = data.get('image_path', None)
            parameters = {}
            if (filepath or image_path) and node.node_id == 'vision-llava-1.6-7b':
                parameters['image_path'] = image_path if image_path else filepath

            query_obj = Query(id=f"query_{int(time.time() * 1000)}", text=prompt,
                              parameters=parameters, history=conversation_history)
            with _INFER_LOCK:
                response = node.process(query_obj)
            return jsonify({'result': response.text, 'response': response.text,
                            'node_id': node.node_id, 'sources': [], 'grounded': False,
                            'processing_time': getattr(response, 'processing_time_ms', 0)})
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return jsonify({'error': f'Query processing failed: {str(e)}'}), 500

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
            return jsonify({'success': True, 'dataset': get_rag_manager().create_dataset(name, data.get('description', ''), files)})
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
            return jsonify({'results': get_rag_manager().search_dataset(dataset_id, query, data.get('top_k', 5))})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return app


if __name__ == '__main__':
    print("=" * 60)
    print("Starting Twhyne AI backend on :5002")
    print("=" * 60)
    app = create_app()
    app.run(host='0.0.0.0', port=5002, debug=False)
