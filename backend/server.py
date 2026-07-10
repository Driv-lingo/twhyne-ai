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
# once segfault the process. All LLM inference goes through this shared lock
# so queries queue up instead of crashing the server. It lives in
# shared_model so deterministic paths (SymPy math) can skip it entirely.
from flux_nodes.shared_model import INFER_LOCK as _INFER_LOCK

# Cancelled client request ids. /query re-checks this after acquiring the
# inference lock, so a job cancelled while QUEUED is skipped instead of
# burning minutes computing an answer nobody will see. (A generation already
# in progress cannot be interrupted mid-token; it finishes and the client
# discards it.)
_CANCELLED = set()
_CANCELLED_LOCK = threading.Lock()


def _is_cancelled(client_rid):
    if not client_rid:
        return False
    with _CANCELLED_LOCK:
        return client_rid in _CANCELLED


# Coarse progress state so the UI can show WHAT the backend is doing
# ("retrieving documents", "generating - code node") instead of a silent
# spinner during multi-minute CPU generations. One query runs at a time
# (inference lock), so a single global is sufficient.
_PROGRESS = {'state': 'idle', 'detail': '', 'since': 0.0}


def _set_progress(state, detail=''):
    _PROGRESS['state'] = state
    _PROGRESS['detail'] = detail
    _PROGRESS['since'] = time.time()

# Cosine-similarity score above which retrieved sources ground the answer.
# BGE cosine scores have a high floor: unrelated query/passage pairs still
# score ~0.53-0.58 (observed: "write a Python function" vs a giraffe manual
# = 0.57), while genuinely relevant pairs score 0.61-0.79. 0.60 splits the
# two bands; 0.30 grounded literally everything.
GROUND_THRESHOLD = 0.60
# AUTO-grounding (no dataset pinned) demands more confidence: benchmark
# showed general questions like "mixing blue and yellow paint" scoring just
# over 0.60 against unrelated business documents, then burning 600s+ of CPU
# on prompt evaluation of irrelevant context. Explicitly attached datasets
# keep the lower bar - the user asserted relevance by attaching them.
GROUND_THRESHOLD_AUTO = 0.64
# Max characters of retrieved context to inject. PDF-extracted text tokenizes
# densely (~1 token per char in bad stretches), so this must leave real
# headroom inside the 8192-token window for the question and the answer.
MAX_CONTEXT_CHARS = 6500
# Auto-grounded answers get a smaller context budget: prompt evaluation on
# CPU is the dominant cost, and marginal chunks add minutes, not accuracy.
MAX_CONTEXT_CHARS_AUTO = 3000


import re
_MATH_RE = re.compile(r'\d\s*[-+*/^=]\s*\d')


def _recent_context(history, cap=600):
    """Last user/assistant exchange, trimmed hard.

    Gives specialists and grounded answers enough memory for follow-ups
    ("now make it recursive", "what about section 5?") without re-inflating
    the prompt toward the token-overflow failures the full history caused.
    """
    if not history:
        return ""
    parts = []
    for msg in history[-2:]:
        role = 'User' if msg.get('role') == 'user' else 'Assistant'
        content = str(msg.get('content', ''))[:cap // 2]
        parts.append(f"{role}: {content}")
    return "\n".join(parts)[:cap]


def _looks_like_math(prompt: str) -> bool:
    """True for queries that are clearly arithmetic/algebra/calculus."""
    p = prompt.lower()
    # Users type unicode operators and thousands separators ("47 × 8,912");
    # normalize them or the math shortcut misses and an LLM guesses at
    # arithmetic - the exact failure SymPy exists to prevent.
    p = (p.replace('×', '*').replace('÷', '/')
          .replace('−', '-').replace('·', '*'))
    p = re.sub(r'(?<=\d),(?=\d)', '', p)
    if _MATH_RE.search(p):
        return True
    kws = ['calculate', 'compute', 'solve', 'derivative', 'integral',
           'integrate', 'differentiate', 'square root', 'divided by',
           'multiplied by', 'plus ', 'minus ', 'times ']
    return any(k in p for k in kws) and any(c.isdigit() or c.isalpha() for c in p)


# Question shapes eligible for the extractive fast path: short, direct
# fact lookups. Summaries, comparisons and open questions still get the LLM.
_FACTOID_RE = re.compile(
    r'^\s*(what|when|who|whom|which|where|how\s+(many|much|long|large|big|often)|'
    r'at\s+what|on\s+which|within|by\s+when|does|do|did|is|are|can|must)\b', re.I)

_STOP_LITE = {"the", "a", "an", "is", "are", "was", "were", "to", "of", "in", "on",
              "at", "by", "for", "with", "and", "or", "what", "which", "who", "how",
              "when", "where", "does", "do", "did", "must", "can", "be", "according"}


_NUM_WORDS_RE = re.compile(
    r'\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|'
    r'fifteen|twenty|thirty|forty|fifty|sixty|ninety|hundred|thousand)\b')


def _span_type_ok(prompt, span):
    """Answer Span Sanity Check: does the span's SHAPE match the question?

    Type compatibility, not literal keyword matching (which would reject
    "encrypted at rest" as an answer to "how must devices be protected?").
    A quantitative question needs a value; "who" needs a role; a yes/no
    question needs permission/prohibition language. Rejection is safe: the
    span falls through to the grounded LLM, never to a refusal.
    """
    pl, sl = prompt.lower(), span.lower()
    if re.search(r'\b(how\s+(many|much|long|large|big)|at\s+what|what\s+time|'
                 r'(on\s+)?which\s+port|within\s+how)\b', pl):
        return bool(re.search(r'\d', sl) or _NUM_WORDS_RE.search(sl))
    if re.match(r'\s*who(m)?\b', pl):
        return bool(re.search(r'\b(administrator|physician|doctor|nurse|manager|'
                              r'director|contact|supervisor|staff|officer|'
                              r'coordinator|family|resident|vendor|team)\b', sl)
                    or any(w[:1].isupper() for w in span.split()[1:]))
    if re.match(r'\s*(can|does|do|did|is|are|must|may|should)\b', pl):
        return bool(re.search(r'\b(must|never|not|no|yes|only|prohibit\w*|'
                              r'requir\w*|permitt\w*|allow\w*|shall|forbid\w*)\b', sl))
    return True


def _extractive_answer(prompt, kept, top_score):
    """Answer a direct fact question with the EXACT source sentence - no LLM.

    This is the strongest form of grounding (a literal quoted span) and it is
    sub-second, versus 15-150s for a 7B generation. Only fires when retrieval
    confidence is high and the question is a short factoid; anything needing
    synthesis falls through to the model. Returns (text, source) or None.
    """
    if top_score < 0.70 or len(prompt) > 140 or not _FACTOID_RE.match(prompt):
        return None
    qwords = {w.strip('?.,!').lower() for w in prompt.split()} - _STOP_LITE
    qwords = {w for w in qwords if len(w) > 2}
    if len(qwords) < 2:
        return None
    wants_value = bool(re.search(
        r'\b(how\s+(many|much|long|large|big)|at\s+what|on\s+which|within|'
        r'what\s+time|which\s+port|score|number|days?|hours?|minutes?)\b',
        prompt, re.I))
    best = None
    for r in kept[:3]:
        for sent in re.split(r'(?<=[.!?])\s+|\n+', r.get('content', '')):
            s = sent.strip().strip('-*# ')
            if not (25 <= len(s) <= 400):
                continue
            words = s.split()
            # Headings restate the question's topic without answering it
            # (benchmark returned "Section 4.2 - Fall Risk Assessment" for
            # "which fall risk scale?"). Skip section labels and title-case
            # runs; an answer span is a sentence, not a label.
            if re.search(r'\bsection\s+\d', s.lower()) and len(words) < 25:
                continue
            titled = sum(1 for w in words if w[:1].isupper())
            if len(words) >= 8 and titled / len(words) > 0.6:
                continue
            if not _span_type_ok(prompt, s):
                continue
            overlap = len(qwords & {w.strip('?.,!').lower() for w in words})
            # A quantitative question is answered by a span with the value.
            if wants_value and re.search(r'\d', s):
                overlap += 2
            if best is None or overlap > best[0]:
                best = (overlap, s, r.get('source', ''))
    if not best or best[0] < 3:
        return None
    _, sentence, source = best
    return (f'"{sentence}" (Source: {source})\n\n'
            f'Exact extract from the source document - no model generation involved.'), source


# Answer cache for document-grounded questions: the same policy question
# asked twice should not pay for retrieval + generation twice. Keyed on the
# normalized question + dataset + document-store version, so any document
# change invalidates every cached answer automatically. Bounded FIFO.
_ANSWER_CACHE = {}
_ANSWER_CACHE_MAX = 256


def _cache_put(key, payload):
    if len(_ANSWER_CACHE) >= _ANSWER_CACHE_MAX:
        _ANSWER_CACHE.pop(next(iter(_ANSWER_CACHE)))
    _ANSWER_CACHE[key] = payload


def _route_query(prompt: str, node_registry) -> Optional[Any]:
    logger.info(f"[ROUTING] Analyzing query: '{prompt}'")
    p = prompt.lower().strip()
    scores = {'math-llm-eval': 0, 'code-codellama-7b': 0, 'planner-mistral-7b': 0,
              'vision-llava-1.6-7b': 0, 'language-mistral-7b': 0}

    # Operator symbols count ONLY between digits ("3+4"). Bare substring
    # matching once routed "tackle/create tech" to the math node on the '/'.
    # Keywords match on WORD BOUNDARIES only: substring matching routed
    # "largest planet" to the planner ('plan') and the Bloops syllogism to
    # the code node ('loop' inside "bloops").
    def _has_kw(kw):
        return re.search(r'\b' + re.escape(kw) + r'\b', p) is not None

    if _looks_like_math(p):
        scores['math-llm-eval'] += 4
    for kw in ['calculate', 'compute', 'solve', 'math', 'equation',
               'derivative', 'integral', 'integrate', 'differentiate']:
        if _has_kw(kw):
            scores['math-llm-eval'] += 2
    for kw in ['code', 'function', 'class', 'method', 'algorithm', 'programming', 'script',
               'debug', 'syntax', 'variable', 'loop', 'python', 'javascript',
               'binary tree', 'linked list', 'recursion', 'recursive', 'array',
               'data structure', 'regex', 'sql']:
        if _has_kw(kw):
            scores['code-codellama-7b'] += 1
    for kw in ['plan', 'schedule', 'organize', 'workflow', 'itinerary', 'trip', 'project', 'timeline', 'roadmap']:
        if _has_kw(kw):
            scores['planner-mistral-7b'] += 1
    for kw in ['image', 'picture', 'photo', 'visual', 'diagram', 'screenshot']:
        if _has_kw(kw):
            scores['vision-llava-1.6-7b'] += 1

    # Registry-loaded custom nodes compete via their declared keywords.
    for node in node_registry.get_all_nodes():
        if node.node_id in scores:
            continue
        kws = getattr(node, 'keywords', None) or []
        s = sum(2 for kw in kws if _has_kw(kw))
        if s:
            scores[node.node_id] = s

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

    # ---- Custom model registry ---------------------------------------
    # Drop any GGUF into the models folder and describe it in nodes.json
    # to add an expert without code changes or a rebuild. Format:
    # backend/nodes.example.json.
    try:
        registry_file = models_dir / 'nodes.json'
        if registry_file.exists():
            import json as _json
            from flux_nodes.custom import CustomLLMNode
            # utf-8-sig: Windows editors (Notepad, PowerShell Out-File)
            # write a BOM, which plain utf-8 JSON parsing rejects.
            for entry in _json.loads(registry_file.read_text(encoding='utf-8-sig')):
                try:
                    n = CustomLLMNode(
                        node_id=entry['node_id'],
                        name=entry.get('name', entry['node_id']),
                        description=entry.get('description', ''),
                        model_path=models_dir / entry['model_file'],
                        keywords=entry.get('keywords', []),
                        prompt_template=entry.get('prompt_template'),
                        n_ctx=int(entry.get('n_ctx', 4096)),
                        max_tokens=int(entry.get('max_tokens', 512)),
                        temperature=float(entry.get('temperature', 0.5)),
                    )
                    node_registry.register_node(n)
                    logger.info(f"Registered custom node: {n.name} ({n.node_id})")
                except Exception as ce:
                    logger.error(f"Failed to load custom node {entry}: {ce}")
    except Exception as e:
        logger.error(f"Custom node registry error: {e}")

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
        """Semantic retrieval. Returns (context, sources, top_score, kept).

        Context is capped so the grounded prompt always fits inside the
        model's context window - and auto-grounded answers get a smaller
        budget, because CPU prompt evaluation is the dominant cost.
        """
        rm = get_rag_manager()
        datasets = rm.list_datasets()
        # Search ALL datasets when none is specified and keep the best
        # evidence overall - with several knowledge bases loaded, searching
        # only the first one grounded questions against the wrong documents.
        ids = [dataset_id] if dataset_id else [d['id'] for d in datasets]
        if not ids:
            return "", [], 0.0, []
        results = []
        for did in ids:
            try:
                results.extend(rm.search_dataset(did, prompt, top_k=8))
            except Exception as e:
                logger.error(f"search failed for dataset {did}: {e}")
        results.sort(key=lambda r: r.get('score', 0), reverse=True)
        results = results[:8]
        if not results:
            return "", [], 0.0, []
        max_chars = MAX_CONTEXT_CHARS if dataset_id else MAX_CONTEXT_CHARS_AUTO
        top_score = results[0]['score']
        kept = [r for r in results if r['score'] >= max(0.2, top_score - 0.15)]
        context, sources = "", []
        for r in kept:
            piece = f"[Source: {r['source']}]\n{r['content']}\n\n"
            if len(context) + len(piece) > max_chars:
                # Add a truncated remainder to stay within budget, then stop.
                remaining = max_chars - len(context)
                if remaining > 200:
                    context += piece[:remaining]
                    if r['source'] not in sources:
                        sources.append(r['source'])
                break
            context += piece
            if r['source'] not in sources:
                sources.append(r['source'])
        return context, sources, top_score, kept

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
            client_rid = str(data.get('client_request_id', '') or '').strip()
            _set_progress('routing')

            from flux_nodes.base import Query

            # ---- DETERMINISTIC TOOLS FIRST -------------------------------
            # Math is exact and instant (SymPy). It must short-circuit BEFORE
            # retrieval so "2+2" never gets swept into the slow grounded path
            # just because a document chunk happens to score above threshold.
            if _looks_like_math(prompt):
                math_node = node_registry.get_node('math-llm-eval')
                if math_node and math_node.is_available:
                    logger.info("Math shortcut: routing directly to SymPy")
                    q = Query(id=f"query_{int(time.time() * 1000)}", text=prompt,
                              parameters={}, history=[])
                    # NO inference lock here: SymPy is instant and must never
                    # queue behind a multi-minute LLM generation (benchmark
                    # once measured 3987s for "3,500 + 4,250" purely from
                    # waiting in line). The node's own LLM fallback for word
                    # problems takes the lock internally.
                    if _is_cancelled(client_rid):
                        return jsonify({'cancelled': True}), 409
                    _set_progress('computing', 'exact math (SymPy)')
                    response = math_node.process(q)
                    return jsonify({'result': response.text, 'response': response.text,
                                    'node_id': 'math-llm-eval', 'sources': [],
                                    'grounded': False})

            # ---- SPECIALIST SHORTCUT -------------------------------------
            # If keyword routing clearly picks a non-language specialist
            # (code/vision/planner) and the caller didn't explicitly attach a
            # dataset, skip retrieval: "Write a Python function" must go to
            # the code model, not get grounded against whatever documents
            # happen to be loaded.
            dataset_id = data.get('dataset_id')
            forced = bool(data.get('use_rag')) or bool(dataset_id)
            if not forced:
                specialist = _route_query(prompt, node_registry)
                # Anything that isn't general language (math was handled
                # above) is a deliberate specialist match - including
                # registry-loaded custom nodes.
                if specialist and specialist.node_id not in (
                        'language-mistral-7b', 'math-llm-eval'):
                    logger.info(f"Specialist shortcut: {specialist.node_id} (skipping retrieval)")
                    parameters = {}
                    image_path = data.get('image_path') or data.get('filepath')
                    if image_path and specialist.node_id == 'vision-llava-1.6-7b':
                        parameters['image_path'] = image_path
                    q = Query(id=f"query_{int(time.time() * 1000)}", text=prompt,
                              parameters=parameters, history=conversation_history)
                    _set_progress('queued', specialist.node_id)
                    with _INFER_LOCK:
                        if _is_cancelled(client_rid):
                            return jsonify({'cancelled': True}), 409
                        _set_progress('generating', specialist.node_id)
                        response = specialist.process(q)
                    return jsonify({'result': response.text, 'response': response.text,
                                    'node_id': specialist.node_id, 'sources': [],
                                    'grounded': False})

            # ---- RETRIEVAL-FIRST ROUTING ---------------------------------
            # Answer cache: only for fresh questions (no conversation
            # context, which changes meaning) against the current document
            # store version.
            cache_key = None
            if not conversation_history:
                try:
                    cache_key = (re.sub(r'\s+', ' ', prompt.strip().lower()),
                                 dataset_id or '*', get_rag_manager().version())
                    hit = _ANSWER_CACHE.get(cache_key)
                    if hit:
                        logger.info("Answer cache hit")
                        return jsonify({**hit, 'cached': True})
                except Exception:
                    cache_key = None

            _set_progress('retrieving documents')
            context, sources, top_score, kept = _retrieve(prompt, dataset_id)
            thr = GROUND_THRESHOLD if forced else GROUND_THRESHOLD_AUTO
            should_ground = forced or (bool(context) and top_score >= thr)

            # Lexical veto for AUTO-grounding: BGE's cosine floor on some
            # corpora sits above the threshold ("reverse a binary tree"
            # scored 0.657 against a Taco Bell 10-K). A genuinely relevant
            # chunk shares at least one meaningful word with the question;
            # a pure embedding-floor artifact shares none.
            if should_ground and not forced and kept:
                pwords = {w for w in re.findall(r'[a-z0-9]+', prompt.lower())
                          if len(w) > 3 and w not in _STOP_LITE}
                top_text = kept[0].get('content', '').lower()
                if pwords and not any(w in top_text for w in pwords):
                    logger.info("Auto-grounding vetoed: no lexical overlap with top chunk")
                    should_ground = False

            if forced and not context:
                msg = "I don't have that in my provided sources."
                return jsonify({'result': msg, 'response': msg,
                                'node_id': 'language-mistral-7b', 'sources': []})

            if should_ground and context:
                # EXTRACTIVE FAST PATH: for a direct fact question with high
                # retrieval confidence, quote the exact source sentence and
                # skip the LLM entirely - sub-second and more pristine than a
                # paraphrase (the answer is a literal, checkable span).
                ext = _extractive_answer(prompt, kept, top_score)
                if ext:
                    text, _src = ext
                    logger.info(f"Extractive answer (top_score={top_score}, no LLM)")
                    if sources:
                        text += "\n\n---\nSources: " + ", ".join(sources)
                    payload = {'result': text, 'response': text,
                               'node_id': 'rag-extractive', 'sources': sources,
                               'grounded': True, 'top_score': top_score,
                               'extractive': True}
                    if cache_key:
                        _cache_put(cache_key, payload)
                    return jsonify(payload)

                logger.info(f"Grounded answer (top_score={top_score}). Sources: {sources}")
                lang = node_registry.get_node('language-mistral-7b')
                recent = _recent_context(conversation_history)
                hist_block = (f"Recent conversation (for reference only):\n{recent}\n\n"
                              if recent else "")
                grounded = (
                    "You are a careful assistant. Answer the question using ONLY the "
                    "information in the sources below, and cite the source name(s). "
                    "If the answer is not fully contained in the sources, say what IS "
                    "supported and note the rest is not in the provided sources. "
                    "Do not add facts that are not in the sources.\n\n"
                    f"{hist_block}"
                    f"Sources:\n{context}\nQuestion: {prompt}\n\nAnswer:"
                )
                # Full conversation history stays out of grounded mode (it
                # caused token overflows); the capped snippet above is enough
                # for follow-up questions.
                q = Query(id=f"query_{int(time.time() * 1000)}", text=grounded,
                          parameters={}, history=[])
                _set_progress('queued', 'grounded answer')
                with _INFER_LOCK:
                    if _is_cancelled(client_rid):
                        return jsonify({'cancelled': True}), 409
                    _set_progress('generating', 'grounded answer with citations')
                    response = lang.process(q)
                text = response.text
                if sources:
                    text += "\n\n---\nSources: " + ", ".join(sources)
                payload = {'result': text, 'response': text,
                           'node_id': 'language-mistral-7b', 'sources': sources,
                           'grounded': True, 'top_score': top_score}
                # Don't cache error text - a transient failure must not
                # become the permanent answer.
                if cache_key and not text.lower().startswith('error'):
                    _cache_put(cache_key, payload)
                return jsonify(payload)

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
            _set_progress('queued', node.node_id)
            with _INFER_LOCK:
                if _is_cancelled(client_rid):
                    return jsonify({'cancelled': True}), 409
                _set_progress('generating', node.node_id)
                response = node.process(query_obj)
            return jsonify({'result': response.text, 'response': response.text,
                            'node_id': node.node_id, 'sources': [], 'grounded': False,
                            'processing_time': getattr(response, 'processing_time_ms', 0)})
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return jsonify({'error': f'Query processing failed: {str(e)}'}), 500
        finally:
            _set_progress('idle')

    @app.route('/progress', methods=['GET'])
    def progress():
        """What the backend is doing right now (for UI progress display)."""
        return jsonify(dict(_PROGRESS))

    @app.route('/cancel', methods=['POST', 'OPTIONS'])
    def cancel_request():
        """Mark a client request id cancelled: if its job is still queued
        behind the inference lock it will be skipped, not computed."""
        if request.method == 'OPTIONS':
            return '', 200
        data = request.get_json() or {}
        rid = str(data.get('client_request_id', '') or '').strip()
        if not rid:
            return jsonify({'error': 'client_request_id required'}), 400
        with _CANCELLED_LOCK:
            _CANCELLED.add(rid)
            if len(_CANCELLED) > 1000:  # bounded memory
                _CANCELLED.clear()
                _CANCELLED.add(rid)
        logger.info(f"Request cancelled: {rid}")
        return jsonify({'cancelled': rid})

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
    try:
        # Production WSGI server. A few threads keep /status, /progress and
        # /cancel responsive while the inference lock serializes generation.
        from waitress import serve
        print("Serving with waitress (production WSGI)")
        serve(app, host='0.0.0.0', port=5002, threads=6)
    except ImportError:
        print("waitress not installed; falling back to Flask dev server")
        app.run(host='0.0.0.0', port=5002, debug=false)
