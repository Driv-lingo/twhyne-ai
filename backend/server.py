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

# Default code model, chosen automatically: Qwen2.5-Coder benchmarked 10/10
# against external unit tests vs CodeLlama's 3/10, so it ships as the
# default. Existing installs with only the CodeLlama file fall back to it -
# no user configuration required either way.
_MODELS_DIR_ = Path(__file__).parent.parent / 'models'
CODE_NODE_ID = 'code-qwen-coder-7b'
CODE_NODE_NAME = 'Code (Qwen2.5-Coder-7B)'
CODE_MODEL_FILE = 'qwen2.5-coder-7b-instruct-q4.gguf'


def _select_code_model():
    """Pick the code model AT RUNTIME (create_app), not import time.

    Import-time selection broke under Docker orderings and, worse, when no
    model file existed the node registered under the deprecated CodeLlama
    identity - so a broken install showed 'Code (CodeLlama-7B) - offline',
    which is wrong twice. Rules: Qwen file -> Qwen; only CodeLlama file ->
    CodeLlama (legacy installs keep working); NEITHER -> keep the modern
    Qwen identity and let the node report unavailable with a message that
    says how to fix it, instead of resurrecting a deprecated name.
    """
    global CODE_NODE_ID, CODE_NODE_NAME, CODE_MODEL_FILE
    qwen = _MODELS_DIR_ / 'qwen2.5-coder-7b-instruct-q4.gguf'
    codellama = _MODELS_DIR_ / 'codellama-7b-q4.gguf'
    if not qwen.exists() and codellama.exists():
        CODE_NODE_ID = 'code-codellama-7b'
        CODE_NODE_NAME = 'Code (CodeLlama-7B)'
        CODE_MODEL_FILE = 'codellama-7b-q4.gguf'
    else:
        CODE_NODE_ID = 'code-qwen-coder-7b'
        CODE_NODE_NAME = 'Code (Qwen2.5-Coder-7B)'
        CODE_MODEL_FILE = 'qwen2.5-coder-7b-instruct-q4.gguf'
    logger.info(f"Code node: {CODE_NODE_NAME} "
                f"({'model present' if (_MODELS_DIR_ / CODE_MODEL_FILE).exists() else 'MODEL MISSING - re-run the launcher to download it'})")


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
           'multiplied by', 'plus ', 'minus ', 'times ',
           # Imperative arithmetic ("Divide 30 by half and add 10") is math,
           # not chat; the digit gate below keeps prose out.
           'divide ', 'by half']
    # A word-operator match needs an actual digit: 'counts how many times
    # target appears' is a coding request, not arithmetic.
    return any(k in p for k in kws) and any(c.isdigit() for c in p)


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
    # 0.66 floor: 0.70 pushed clear factoids ("insulin window before meals")
    # into 5-minute generations; the span checks below are the real guard.
    if top_score < 0.66 or len(prompt) > 160 or not _FACTOID_RE.match(prompt):
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
            f'Exact extract from the source document - no model generation involved.'), source, sentence


POLICY_CONSOLE_HTML = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Twhyne - Policy & Identity</title>
<style>
:root{--bg:#07060b;--panel:#141020;--line:rgba(157,123,255,.16);--fg:#efeaf7;--muted:#a99fc0;
--violet:#9d7bff;--wine:#d34a67;--verify:#3ce88f;--refuse:#ff7a6b}
*{box-sizing:border-box;margin:0}body{background:var(--bg);color:var(--fg);
font-family:ui-sans-serif,system-ui,sans-serif;padding:28px;line-height:1.5}
.wrap{max-width:900px;margin:0 auto}h1{font-size:22px;margin-bottom:4px}
.sub{color:var(--muted);font-size:14px;margin-bottom:22px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:20px;margin-bottom:16px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:12px;
font-family:ui-monospace,monospace}
label{display:block;font-size:12px;color:var(--muted);margin:10px 0 4px;font-family:ui-monospace,monospace}
input,textarea,select{width:100%;background:#0e0b16;border:1px solid var(--line);border-radius:6px;
color:var(--fg);padding:9px 11px;font-family:ui-monospace,monospace;font-size:13px}
textarea{min-height:230px;white-space:pre;overflow-wrap:normal;overflow-x:auto}
button{background:linear-gradient(96deg,var(--wine),var(--violet));color:#fff;border:0;border-radius:6px;
padding:10px 16px;font-weight:600;cursor:pointer;font-family:ui-monospace,monospace;margin-top:12px}
button.ghost{background:transparent;border:1px solid var(--line);color:var(--fg)}
.row{display:flex;gap:10px;flex-wrap:wrap}.row>*{flex:1;min-width:150px}
.msg{margin-top:12px;font-family:ui-monospace,monospace;font-size:13px;padding:9px 12px;border-radius:6px;display:none}
.msg.ok{display:block;background:rgba(60,232,143,.1);color:var(--verify);border:1px solid rgba(60,232,143,.4)}
.msg.err{display:block;background:rgba(255,122,107,.1);color:var(--refuse);border:1px solid rgba(255,122,107,.4)}
code{background:#0e0b16;padding:2px 6px;border-radius:4px;font-size:12px;color:var(--violet)}
.tok{word-break:break-all;font-size:12px;color:var(--verify);margin-top:8px}
</style></head><body><div class="wrap">
<h1>Twhyne &mdash; Policy &amp; Identity Console</h1>
<div class="sub">Edit the access policy and mint signed identity tokens. Runs against this local runtime.</div>

<div class="card"><h2>Admin token</h2>
<div class="sub" style="margin:0 0 8px">Required when the runtime has <code>TWHYNE_ADMIN_TOKEN</code> set. Stored only in this tab.</div>
<input id="admtok" type="password" placeholder="X-Admin-Token (leave blank on fresh install)"></div>

<div class="card"><h2>Access policy</h2>
<div class="sub" style="margin:0 0 6px">Governs retrieval AND compute. <code>sources</code> = who can read which documents; <code>node_roles</code> = which roles may invoke which expert nodes (supports <code>"code-*"</code> family rules); <code>node_default_allowed</code> = false locks every unlisted node down. Edit the JSON, then save.</div>
<textarea id="policy" spellcheck="false"></textarea>
<div class="row"><button class="ghost" onclick="loadPolicy()">Reload</button><button onclick="savePolicy()">Save policy</button></div>
<div class="msg" id="pmsg"></div></div>

<div class="card"><h2>Models &amp; nodes</h2>
<div class="sub" style="margin:0 0 10px">Import a Hugging Face GGUF as a live expert node, set which roles may invoke it, and manage existing nodes. Imports register live &mdash; no restart.</div>
<div class="row">
<div><label>Hugging Face .gguf URL</label><input id="murl" placeholder="https://huggingface.co/&hellip;/model.Q4_K_M.gguf"></div>
</div>
<div class="row">
<div><label>Node id (lowercase)</label><input id="mid" placeholder="hf-medical-7b"></div>
<div><label>Display name</label><input id="mname" placeholder="Medical QA 7B"></div>
</div>
<div class="row">
<div><label>Keywords (comma-sep, for routing)</label><input id="mkw" placeholder="medical, clinical, diagnosis"></div>
<div><label>Allowed roles (comma-sep; blank = all)</label><input id="mroles" placeholder="nurse, admin"></div>
</div>
<button onclick="addModel()">Import model</button>
<div class="msg" id="mmsg"></div>
<div id="jobs" style="margin-top:12px"></div>
<div id="nodelist" style="margin-top:14px"></div>
</div>

<div class="card"><h2>Mint identity token</h2>
<div class="sub" style="margin:0 0 6px">A signed token binds a user to a role. Send it as <code>Authorization: Bearer &lt;token&gt;</code>; it cannot be overridden by a request body.</div>
<div class="row">
<div><label>Subject (user id / email)</label><input id="subj" placeholder="nurse@facility"></div>
<div><label>Role</label><select id="role">
<option>public</option><option>staff</option><option>nurse</option><option>family_contact</option>
<option>it_admin</option><option>auditor</option><option>admin</option></select></div>
</div>
<button onclick="mint()">Issue token</button>
<div class="msg" id="imsg"></div><div class="tok" id="tok"></div></div>

</div><script>
function hdrs(){var h={'Content-Type':'application/json'};var t=document.getElementById('admtok').value.trim();
if(t)h['X-Admin-Token']=t;return h;}
function msg(id,t,k){var m=document.getElementById(id);m.textContent=t;m.className='msg '+k;}
async function loadPolicy(){try{var r=await fetch('/api/permissions');var d=await r.json();
document.getElementById('policy').value=JSON.stringify(d,null,2);msg('pmsg','Loaded current policy.','ok');}
catch(e){msg('pmsg','Could not load: '+e,'err');}}
async function savePolicy(){var raw=document.getElementById('policy').value;var body;
try{body=JSON.parse(raw);}catch(e){msg('pmsg','Invalid JSON: '+e.message,'err');return;}
try{var r=await fetch('/api/permissions',{method:'POST',headers:hdrs(),body:JSON.stringify(body)});
var d=await r.json();if(r.ok&&d.success){msg('pmsg','Policy saved and active.','ok');}
else{msg('pmsg',d.error||'Save failed','err');}}catch(e){msg('pmsg','Error: '+e,'err');}}
async function mint(){var subject=document.getElementById('subj').value.trim();
var role=document.getElementById('role').value;if(!subject){msg('imsg','Enter a subject.','err');return;}
try{var r=await fetch('/api/identity/token',{method:'POST',headers:hdrs(),
body:JSON.stringify({subject:subject,role:role})});var d=await r.json();
if(r.ok&&d.token){msg('imsg','Token issued for '+subject+' ('+role+'), valid '+(d.expires_in/3600)+'h.','ok');
document.getElementById('tok').textContent=d.token;}
else{msg('imsg',d.error||'Failed','err');document.getElementById('tok').textContent='';}}
catch(e){msg('imsg','Error: '+e,'err');}}
// ---- models & nodes ----
function csv(id){return document.getElementById(id).value.split(',').map(function(s){return s.trim();}).filter(Boolean);}
async function addModel(){
var url=document.getElementById('murl').value.trim();var nid=document.getElementById('mid').value.trim();
if(!url||!nid){msg('mmsg','URL and node id are required.','err');return;}
var body={url:url,node_id:nid,name:document.getElementById('mname').value.trim()||nid,
keywords:csv('mkw'),allowed_roles:csv('mroles')};
try{var r=await fetch('/api/models/add',{method:'POST',headers:hdrs(),body:JSON.stringify(body)});
var d=await r.json();if(r.status===202){msg('mmsg','Import started for '+nid+' - downloading&hellip;','ok');pollJobs();}
else{msg('mmsg',d.error||'Import failed','err');}}catch(e){msg('mmsg','Error: '+e,'err');}}
var jobTimer=null;
async function pollJobs(){try{var r=await fetch('/api/models/jobs');var d=await r.json();
var jobs=d.jobs||{};var html='';var active=false;
Object.keys(jobs).forEach(function(k){var j=jobs[k];if(j.state!=='ready'&&j.state!=='error')active=true;
html+='<div style="font-family:ui-monospace,monospace;font-size:12px;color:var(--muted);margin:3px 0">'+
esc2(j.node_id||k)+': '+esc2(j.state)+' '+(j.pct!=null?Math.round(j.pct)+'%':'')+' '+esc2(j.msg||'')+'</div>';});
document.getElementById('jobs').innerHTML=html;
if(active){if(jobTimer)clearTimeout(jobTimer);jobTimer=setTimeout(pollJobs,1500);}else{loadNodes();}}catch(e){}}
function esc2(s){return (s==null?'':String(s)).replace(/&/g,'&amp;').replace(/</g,'&lt;');}
async function loadNodes(){try{var r=await fetch('/api/models');var d=await r.json();var m=d.models||[];
var html='<label>Live nodes</label>';
m.forEach(function(n){var roles=(n.allowed_roles||[]).join(', ')||'all roles';
html+='<div style="display:flex;gap:8px;align-items:center;border:1px solid var(--line);border-radius:6px;padding:8px 10px;margin:6px 0">'+
'<div style="flex:1"><code>'+esc2(n.node_id)+'</code> <span style="color:var(--muted);font-size:12px">'+
(n.builtin?'built-in':'imported')+' &middot; roles: '+esc2(roles)+'</span></div>'+
'<input id="nr_'+esc2(n.node_id)+'" placeholder="roles csv" style="max-width:180px;font-size:12px;padding:5px 8px">'+
'<button class="ghost" style="margin:0;padding:6px 10px;font-size:12px" onclick="setRoles(\''+esc2(n.node_id)+'\')">Set roles</button>'+
(n.builtin?'':'<button class="ghost" style="margin:0;padding:6px 10px;font-size:12px" onclick="delNode(\''+esc2(n.node_id)+'\')">Delete</button>')+
'</div>';});
document.getElementById('nodelist').innerHTML=html;}catch(e){}}
async function setRoles(nid){var roles=document.getElementById('nr_'+nid).value.split(',').map(function(s){return s.trim();}).filter(Boolean);
if(!roles.length){msg('mmsg','Enter at least one role (or use Delete to clear).','err');return;}
try{var r=await fetch('/api/models/'+encodeURIComponent(nid)+'/roles',{method:'PUT',headers:hdrs(),
body:JSON.stringify({allowed_roles:roles})});var d=await r.json();
if(r.ok&&d.success){msg('mmsg','Roles for '+nid+' set to: '+roles.join(', '),'ok');loadNodes();}
else{msg('mmsg',d.error||'Failed','err');}}catch(e){msg('mmsg','Error: '+e,'err');}}
async function delNode(nid){if(!confirm('Remove node '+nid+'?'))return;
try{var r=await fetch('/api/models/'+encodeURIComponent(nid),{method:'DELETE',headers:hdrs()});
var d=await r.json();if(r.ok){msg('mmsg','Removed '+nid,'ok');loadNodes();}else{msg('mmsg',d.error||'Failed','err');}}
catch(e){msg('mmsg','Error: '+e,'err');}}
loadPolicy();loadNodes();
</script></body></html>"""


def _evidence_records(kept, span=None, span_source=None):
    """Typed evidence records for the chunks an answer drew on.

    References only - source name, chunk index, content hash, retrieval
    score - never the content itself, so the records are safe to return,
    log, and chain into the audit ledger. `span` marks the exact quoted
    sentence for extractive answers.
    """
    recs = []
    for r in kept[:6]:
        rec = {
            'source': r.get('source', ''),
            'chunk_index': r.get('chunk_index', 0),
            'content_sha': _hashlib.sha256(
                (r.get('content') or '').encode()).hexdigest()[:16],
            'score': round(float(r.get('score') or 0), 3),
            'retrieval': 'semantic',
        }
        if span and r.get('source') == span_source and span in (r.get('content') or ''):
            rec['span'] = span[:300]
            rec['support'] = 'quoted'
        recs.append(rec)
    return recs


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
    scores = {'math-llm-eval': 0, CODE_NODE_ID: 0, 'planner-mistral-7b': 0,
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
            scores[CODE_NODE_ID] += 1
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


# OUTPUT-SIDE SECRET VETO (defense in depth, independent of retrieval).
# The retrieval-side restriction (rag_manager) hides documents that DECLARE
# themselves confidential - but a secret in an unmarked document, or reached
# any other way, would slip past it. This second layer scans the FINAL answer
# for secret-SHAPED content and redacts before it leaves the server, no
# matter how it got there. It is heuristic, not a guarantee: it raises the
# bar, it does not replace a real permission model.
_SECRET_PATTERNS = [
    re.compile(r'\b[A-Z0-9]{2,}(?:-[A-Z0-9]{2,}){2,}\b'),                 # XK9-BENCH-SECRET-42
    re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),                                # US SSN
    re.compile(r'\b(?:sk|pk|api|key|token|bearer)[-_][A-Za-z0-9]{12,}\b', re.I),
    re.compile(r'\b[A-Za-z0-9]{20,}\b'),                                  # long opaque token
]
# Secret/credential CONTEXT: a value adjacent to these words is likely a leak.
_SECRET_CONTEXT = re.compile(
    r'\b(password|passphrase|secret|api[\s_-]?key|private[\s_-]?key|'
    r'token|credential|ssn|social security)\b', re.I)
_MONEY_SALARY = re.compile(r'\b(salary|earns?|compensation|paid)\b.{0,40}?\$?[\d,]{4,}', re.I)


def _scrub_secrets(text):
    """Redact secret-shaped substrings from a final answer. Returns
    (scrubbed_text, hit_count)."""
    if not text:
        return text, 0
    hits = 0
    # Only scan for opaque tokens when the surrounding text talks about
    # credentials/secrets, to avoid nuking legitimate identifiers.
    credentialish = bool(_SECRET_CONTEXT.search(text))
    for pat in _SECRET_PATTERNS:
        if pat is _SECRET_PATTERNS[-1] and not credentialish:
            continue  # the broad "long token" rule only fires in secret context
        def _sub(m):
            nonlocal hits
            hits += 1
            return "[REDACTED]"
        text = pat.sub(_sub, text)
    if _MONEY_SALARY.search(text) and _SECRET_CONTEXT.search(text) is None:
        # salary-in-context (restricted personnel data)
        text, n = _MONEY_SALARY.subn(lambda m: m.group(0).split('$')[0] + "[REDACTED]", text)
        hits += n
    return text, hits


# ---- Immutable audit ledger (tamper-evident, hash-chained) ----------
# Every answered query appends one record whose hash chains to the previous
# record's hash (like a mini blockchain / git log). Any later edit to a past
# record breaks the chain from that point on, so tampering is DETECTABLE even
# though the file is a plain append-only JSONL. This is the "auditable, not
# incorruptible" property: we can prove whether the log was altered.
import hashlib as _hashlib
import hmac as _hmac


def _hmac_equal(a, b):
    """Constant-time string comparison for admin-token checks."""
    return _hmac.compare_digest(str(a), str(b))


def _require_admin():
    """Return a 401 response if TWHYNE_ADMIN_TOKEN is set and not matched,
    else None (open on a fresh install with no token). Import-safe: uses the
    request in scope. Callers: `deny = _require_admin(); if deny: return deny`.
    """
    from flask import request as _rq, jsonify as _js
    token = os.environ.get('TWHYNE_ADMIN_TOKEN', '').strip()
    if not token:
        return None
    supplied = _rq.headers.get('X-Admin-Token', '').strip()
    if not supplied or not _hmac_equal(supplied, token):
        return _js({'error': 'Unauthorized - admin token required'}), 401
    return None

_AUDIT_LOCK = _threading.Lock() if False else __import__('threading').Lock()
_AUDIT_PATH = Path(os.environ.get(
    'TWHYNE_AUDIT_LOG',
    str(Path(__file__).parent / 'rag_storage' / 'audit_ledger.jsonl')))


def _audit_last_hash():
    try:
        if not _AUDIT_PATH.exists():
            return '0' * 64
        with open(_AUDIT_PATH, 'rb') as f:
            last = b''
            for line in f:
                if line.strip():
                    last = line
        if not last:
            return '0' * 64
        return __import__('json').loads(last).get('hash', '0' * 64)
    except Exception:
        return '0' * 64


def _audit_append(event):
    """Append one hash-chained audit record. Never raises into the request."""
    try:
        import json as _json
        _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _AUDIT_LOCK:
            prev = _audit_last_hash()
            rec = {
                'ts': time.time(),
                'prev': prev,
                'role': event.get('role'),
                'prompt_sha': _hashlib.sha256(
                    (event.get('prompt') or '').encode()).hexdigest()[:16],
                'node_id': event.get('node_id'),
                'sources': event.get('sources') or [],
                'verdict': event.get('verdict'),
                'redacted': bool(event.get('redacted')),
                'cached': bool(event.get('cached')),
                # Structured gate record + evidence references (hashes and
                # source names only - never document content).
                'gates': event.get('gates'),
                'evidence': event.get('evidence'),
            }
            # hash covers the record body + the previous hash => chain
            body = _json.dumps(rec, sort_keys=True)
            rec['hash'] = _hashlib.sha256((prev + body).encode()).hexdigest()
            with open(_AUDIT_PATH, 'a') as f:
                f.write(_json.dumps(rec) + '\n')
    except Exception as e:
        logger.error(f"audit append failed: {e}")


def _audit_verify():
    """Walk the chain; return (ok, count, first_broken_index)."""
    import json as _json
    if not _AUDIT_PATH.exists():
        return True, 0, None
    prev = '0' * 64
    n = 0
    with open(_AUDIT_PATH) as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            rec = _json.loads(line)
            stored = rec.pop('hash', None)
            body = _json.dumps({k: rec[k] for k in rec if k != 'hash'}, sort_keys=True)
            calc = _hashlib.sha256((rec.get('prev', '') + body).encode()).hexdigest()
            if rec.get('prev') != prev or calc != stored:
                return False, n, i
            prev = stored
            n += 1
    return True, n, None


# ---- Layer 9 v0.1: governed timers (`timer.notify`) -------------------
# The one whitelisted action capability. Design constraints, in order:
#   * consent at request time - a timer exists only because a caller asked;
#   * fail-closed - no `timer.notify` policy in permissions => denied;
#   * bounded - per-role pending cap and max duration from the policy;
#   * ZERO autonomous action - a timer "fires" at READ TIME: its state is
#     computed from the clock when the list is observed (the UI polling on
#     the user's behalf counts as the user asking). No background thread,
#     no unprompted notification. Deferred state + polling observer.
#   * audited - creation, first-observed elapse, and cancellation are
#     hash-chained ledger records like any query.

_TIMERS_PATH = _AUDIT_PATH.parent / 'timers.json'
_TIMERS_LOCK = __import__('threading').Lock()


def _timers_load():
    import json as _json
    try:
        if _TIMERS_PATH.exists():
            return _json.loads(_TIMERS_PATH.read_text()) or []
    except Exception as e:
        logger.error(f"timers load failed: {e}")
    return []


def _timers_save(timers):
    import json as _json
    try:
        _TIMERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _TIMERS_PATH.write_text(_json.dumps(timers, indent=1))
    except Exception as e:
        logger.error(f"timers save failed: {e}")


_LABEL_SAFE_RE = __import__('re').compile(r'[^A-Za-z0-9 .,:\-]')


def _safe_label(label):
    """Labels are echoed into chat, and chat re-enters LLM prompts via
    conversation history — so a label is an INJECTION SURFACE, not just a
    string. Strict charset, collapsed whitespace, hard cap. Never store a
    raw prompt as a label.
    """
    s = _LABEL_SAFE_RE.sub(' ', str(label or ''))
    return ' '.join(s.split())[:60]


def _timer_audit(action, timer, role):
    _audit_append({
        'role': role,
        'prompt': f"action:{action}:{timer.get('id')}",
        'node_id': 'action-policy',
        'verdict': action,
        'gates': {'action': 'timer.notify', 'event': action,
                  'timer_id': timer.get('id'),
                  'label': timer.get('label'),
                  'due_at': timer.get('due_at')},
    })


def _timer_create(role, seconds, label='', subject=None):
    """Create a timer under the `timer.notify` action policy.

    `subject` is the SIGNED identity subject (None when unsigned). Timers
    belong to a subject when one exists; unsigned timers belong to the
    shared role bucket and are second-class by design.

    Returns (timer, None) or (None, (http_status, message)). Every denial
    reason is stated - the caller can show it verbatim.
    """
    policy = get_rag_manager().action_policy('timer.notify')
    if policy is None:
        return None, (403, "The 'timer.notify' action is not permitted by "
                           "this install's action policy.")
    allowed = policy.get('allowed_roles') or []
    if '*' not in allowed and role not in allowed:
        return None, (403, f"Role '{role}' is not authorized for "
                           f"'timer.notify'.")
    try:
        seconds = float(seconds)
    except Exception:
        return None, (400, 'duration_seconds must be a number.')
    max_s = float(policy.get('max_duration_hours', 24)) * 3600
    if not (0 < seconds <= max_s):
        return None, (400, f"Duration must be between 1 second and "
                           f"{policy.get('max_duration_hours', 24)} hours.")
    import uuid as _uuid
    with _TIMERS_LOCK:
        timers = _timers_load()
        pending = [t for t in timers
                   if _timer_owned(t, role, subject)
                   and t.get('status') == 'pending']
        cap = int(policy.get('max_pending_per_role', 5))
        if len(pending) >= cap:
            return None, (429, f"Pending-timer cap reached for role "
                               f"'{role}' ({cap}).")
        now = time.time()
        timer = {'id': _uuid.uuid4().hex[:12], 'role': role,
                 'subject': subject,
                 'label': _safe_label(label),
                 'created_at': now, 'due_at': now + seconds,
                 'duration_seconds': seconds,
                 'status': 'pending', 'fired_at': None}
        timers.append(timer)
        _timers_save(timers)
    _timer_audit('timer-created', timer, role)
    return timer, None


def _timer_owned(t, role, subject):
    """Ownership check. Timers are PERSON-scoped when a signed subject
    exists; a body-asserted role can neither see nor cancel them (claiming
    a role must never claim a person's resources). Unsigned timers live in
    a shared per-role bucket visible only to other unsigned callers of
    that role - the honest semantics of an unauthenticated dev install.
    """
    if t.get('subject'):
        return subject is not None and t.get('subject') == subject
    return subject is None and t.get('role') == role


def _timers_observe(role=None, subject=None):
    """Read-time firing: recompute each timer's state from the clock NOW,
    because someone is looking. First observation past due_at transitions
    pending -> elapsed and audits the event; nothing happens between reads.
    Returns the caller's own timers, newest first.
    """
    fired = []
    with _TIMERS_LOCK:
        timers = _timers_load()
        now = time.time()
        for t in timers:
            if t.get('status') == 'pending' and now >= float(t.get('due_at') or 0):
                t['status'] = 'elapsed'
                t['fired_at'] = now
                fired.append(t)
        # Housekeeping at read time (still observation-driven, no background
        # work): finished timers older than 7 days leave the working store.
        # Their creation/elapse records remain in the audit ledger forever.
        cutoff = now - 7 * 86400
        kept = [t for t in timers
                if t.get('status') == 'pending'
                or float(t.get('fired_at') or t.get('created_at') or 0) >= cutoff]
        if fired or len(kept) != len(timers):
            timers = kept
            _timers_save(timers)
    for t in fired:
        _timer_audit('timer-elapsed', t, t.get('role'))
    out = [t for t in timers if _timer_owned(t, role, subject)]
    return sorted(out, key=lambda t: t.get('created_at') or 0, reverse=True)


# ---- Alert escalation: notify a person, not just a log ---------------
# Local-first means nothing leaves by default; escalation only goes where
# the operator explicitly points it:
#   TWHYNE_ALERT_WEBHOOK  https URL that receives a JSON POST per alert
#                         (generic; works with Slack/Teams incoming webhooks)
#   TWHYNE_ALERT_EMAIL    address to notify via local SMTP
#   TWHYNE_SMTP_HOST/PORT SMTP relay for the above (default localhost:25)
# Alerts are throttled (same type+subject at most once per hour) so a
# probing loop pages a human once, not five hundred times.

_ESCALATE_LOCK = __import__('threading').Lock()
_ESCALATE_LAST = {}  # (type, subject) -> monotonic seconds of last send
_ESCALATE_THROTTLE_S = int(os.environ.get('TWHYNE_ALERT_THROTTLE_S', '3600') or 3600)


def _escalate_alert(alert):
    """Push one alert to the configured webhook/email. Never raises.

    `alert` is the same shape the admin console shows: severity, type,
    what, why, subject. Content is metadata only — prompts are referenced
    by hash in the audit ledger, never included here.
    """
    webhook = os.environ.get('TWHYNE_ALERT_WEBHOOK', '').strip()
    email_to = os.environ.get('TWHYNE_ALERT_EMAIL', '').strip()
    if not webhook and not email_to:
        return False
    key = (alert.get('type'), alert.get('subject'))
    now = time.monotonic()
    with _ESCALATE_LOCK:
        last = _ESCALATE_LAST.get(key)
        if last is not None and now - last < _ESCALATE_THROTTLE_S:
            return False
        _ESCALATE_LAST[key] = now
    sent = False
    if webhook:
        try:
            import json as _json
            body = _json.dumps({
                'source': 'twhyne',
                'severity': alert.get('severity'),
                'type': alert.get('type'),
                'what': alert.get('what'),
                'why': alert.get('why'),
                'subject': alert.get('subject'),
                # Slack/Teams render `text`; other receivers use the fields.
                'text': f"[TWHYNE {str(alert.get('severity','')).upper()}] "
                        f"{alert.get('what')} — {alert.get('why')}",
            }).encode()
            req = _urlreq.Request(webhook, data=body,
                                  headers={'Content-Type': 'application/json'})
            _urlreq.urlopen(req, timeout=6)
            sent = True
        except Exception as e:
            logger.error(f"alert webhook failed: {e}")
    if email_to:
        try:
            import smtplib
            from email.message import EmailMessage
            msg = EmailMessage()
            msg['Subject'] = (f"[Twhyne {str(alert.get('severity','')).upper()}] "
                              f"{alert.get('type')}")
            msg['From'] = os.environ.get('TWHYNE_ALERT_FROM', 'twhyne@localhost')
            msg['To'] = email_to
            msg.set_content(f"{alert.get('what')}\n\nWhy this matters:\n"
                            f"{alert.get('why')}\n\nSubject: {alert.get('subject')}\n"
                            f"Review the admin alerts feed for detail.")
            host = os.environ.get('TWHYNE_SMTP_HOST', 'localhost')
            port = int(os.environ.get('TWHYNE_SMTP_PORT', '25') or 25)
            with smtplib.SMTP(host, port, timeout=8) as s:
                s.send_message(msg)
            sent = True
        except Exception as e:
            logger.error(f"alert email failed: {e}")
    if sent:
        logger.warning(f"escalated alert: {alert.get('type')} ({alert.get('severity')})")
    return sent


# ---- License heartbeat: periodic re-validation + safety counters -----
# The container validates its key once at startup; this loop re-validates
# every TWHYNE_HEARTBEAT_S (default 6h) so a revoked key actually bites,
# and ships SAFETY COUNTERS with the ping: number of redaction events,
# permission refusals, audit-chain status, record count, version. Counters
# only — prompts and documents never leave the machine (they are referenced
# by hash in the local ledger). This is the disclosed mechanism by which
# Twhyne can spot abusive deployments. Disable with TWHYNE_HEARTBEAT_S=0.

_HEARTBEAT_STATE = {'last_ts': 0.0, 'license_valid': True, 'message': ''}

# Enforcement: once the license server EXPLICITLY reports the key invalid
# (revoked/expired — not merely offline), a grace timer starts. After
# TWHYNE_REVOKE_GRACE_H (default 72h) /query is blocked until a valid ping
# clears it. Offline never triggers enforcement: air-gapped installs are a
# supported deployment, and the startup gate in docker-entrypoint.sh already
# refuses to boot on a key the server rejects. State is persisted (HMAC'd
# with the license key) so a restart doesn't reset the grace clock.
_LICENSE_STATE_PATH = Path(os.environ.get(
    'TWHYNE_LICENSE_STATE',
    str(Path(__file__).parent / 'rag_storage' / 'license_state.json')))


def _license_state_sig(payload: str) -> str:
    key = os.environ.get('SNF_LICENSE_KEY', '').strip()
    return _hashlib.sha256((payload + '|' + key).encode()).hexdigest()


def _load_license_state():
    """{'first_invalid_ts': float|None} — verified against its signature."""
    import json as _json
    try:
        raw = _json.loads(_LICENSE_STATE_PATH.read_text())
        payload = _json.dumps(raw.get('state'), sort_keys=True)
        if _hmac.compare_digest(raw.get('sig', ''), _license_state_sig(payload)):
            return raw.get('state') or {}
    except Exception:
        pass
    return {}


def _save_license_state(state):
    import json as _json
    try:
        _LICENSE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = _json.dumps(state, sort_keys=True)
        _LICENSE_STATE_PATH.write_text(_json.dumps(
            {'state': state, 'sig': _license_state_sig(payload)}))
    except Exception as e:
        logger.error(f"license state save failed: {e}")


def _license_blocked():
    """(blocked, message). True once the revocation grace window has lapsed."""
    grace_h = float(os.environ.get('TWHYNE_REVOKE_GRACE_H', '72') or 72)
    state = _load_license_state()
    first = state.get('first_invalid_ts')
    if not first:
        return False, ''
    remaining = grace_h * 3600 - (time.time() - float(first))
    if remaining > 0:
        return False, (f"License invalid — service continues for "
                       f"{int(remaining // 3600)}h grace. Renew at twhyne.com.")
    return True, ("This deployment's license was revoked or expired and the "
                  "grace period has ended. Renew at twhyne.com or contact "
                  "support; queries are disabled until the key validates.")


def _audit_counters_since(ts):
    """(redactions, refusals, records) from ledger entries newer than ts."""
    import json as _json
    red = ref = total = 0
    try:
        if _AUDIT_PATH.exists():
            with open(_AUDIT_PATH) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = _json.loads(line)
                    except Exception:
                        continue
                    if float(rec.get('ts') or 0) <= ts:
                        continue
                    total += 1
                    if rec.get('redacted'):
                        red += 1
                    if str(rec.get('verdict') or '').lower() == 'refused':
                        ref += 1
    except Exception as e:
        logger.error(f"heartbeat counter scan failed: {e}")
    return red, ref, total


def _machine_id(key):
    """Stable, non-reversible device id for this install.

    Prefers a persisted uuid under the models/rag volume (survives image
    updates), falls back to /etc/machine-id, then the hostname. Hashed with
    the license key so the same hardware under two keys reads as two
    devices and the raw machine id never leaves the box.
    """
    seed = None
    try:
        idfile = Path(os.environ.get(
            'TWHYNE_LICENSE_STATE',
            str(Path(__file__).parent / 'rag_storage' / 'license_state.json'))
        ).parent / 'device_id'
        if idfile.exists():
            seed = idfile.read_text().strip()
        else:
            import uuid
            seed = uuid.uuid4().hex
            try:
                idfile.parent.mkdir(parents=True, exist_ok=True)
                idfile.write_text(seed)
            except Exception:
                pass
    except Exception:
        seed = None
    if not seed:
        for p in ('/etc/machine-id', '/var/lib/dbus/machine-id'):
            try:
                seed = Path(p).read_text().strip()
                if seed:
                    break
            except Exception:
                continue
    seed = seed or os.environ.get('HOSTNAME', 'unknown')
    return _hashlib.sha256((seed + '|' + key).encode()).hexdigest()[:32]


def _license_heartbeat_once():
    """One validation ping with safety counters. Never raises."""
    key = os.environ.get('SNF_LICENSE_KEY', '').strip()
    api = os.environ.get('LICENSE_API_URL', 'https://twhyne.com').rstrip('/')
    if not key:
        return
    import json as _json
    red, ref, total = _audit_counters_since(_HEARTBEAT_STATE['last_ts'])
    chain_ok, _, _ = _audit_verify()
    body = _json.dumps({
        'license_key': key,
        # Stable per-install device id so the account page shows real
        # devices. Derived from the license key + the machine's id (mounted
        # from the host, else the container's) - stable across restarts,
        # and non-reversible (a hash, never the raw machine id).
        'machine_id': _machine_id(key),
        'telemetry': {
            'redactions': red,
            'refusals': ref,
            'tamper': not chain_ok,
            'records': total,
            'version': os.environ.get('TWHYNE_VERSION', 'dev'),
        },
    }).encode()
    try:
        req = _urlreq.Request(api + '/api/validate', data=body,
                              headers={'Content-Type': 'application/json'})
        with _urlreq.urlopen(req, timeout=10) as resp:
            payload = _json.loads(resp.read().decode() or '{}')
        _HEARTBEAT_STATE['last_ts'] = time.time()
        if not payload.get('valid', True):
            _HEARTBEAT_STATE['license_valid'] = False
            _HEARTBEAT_STATE['message'] = payload.get('message', 'invalid')
            # Anchor the grace clock to the server's timestamp when given, so
            # deleting the local state file cannot restart the countdown.
            server_ts = None
            try:
                iso = payload.get('invalid_since')
                if iso:
                    from datetime import datetime as _dt
                    server_ts = _dt.fromisoformat(str(iso)).timestamp()
            except Exception:
                server_ts = None
            state = _load_license_state()
            candidates = [t for t in (state.get('first_invalid_ts'),
                                      server_ts, time.time()) if t]
            first = min(candidates)
            if state.get('first_invalid_ts') != first:
                _save_license_state({'first_invalid_ts': first})
            logger.error(f"LICENSE INVALID: {payload.get('message')} — "
                         f"contact twhyne.com; this deployment is out of terms.")
            _escalate_alert({
                'severity': 'high', 'type': 'license-invalid',
                'what': f"License check failed: {payload.get('message')}.",
                'why': 'The key was revoked or expired. The system keeps '
                       'serving to avoid disrupting care/operations, but the '
                       'deployment is no longer licensed.',
                'subject': key[-9:],
            })
        else:
            _HEARTBEAT_STATE['license_valid'] = True
            _HEARTBEAT_STATE['message'] = 'ok'
            if _load_license_state().get('first_invalid_ts'):
                _save_license_state({})  # revocation cleared (renewed key)
    except Exception as e:
        # Offline is fine — local-first must keep working without internet.
        logger.info(f"license heartbeat skipped (offline?): {e}")


def _start_license_heartbeat():
    interval = int(os.environ.get('TWHYNE_HEARTBEAT_S', '21600') or 0)
    if interval <= 0 or not os.environ.get('SNF_LICENSE_KEY', '').strip():
        return
    def loop():
        # First ping shortly after boot so counters/revocations surface fast,
        # then every interval.
        time.sleep(60)
        while True:
            _license_heartbeat_once()
            time.sleep(interval)
    t = __import__('threading').Thread(target=loop, daemon=True,
                                       name='license-heartbeat')
    t.start()
    logger.info(f"license heartbeat every {interval}s (counters only)")


# ---- Model pipeline: add a Hugging Face GGUF as a live node ----------
# The custom-node registry already lets a GGUF become an expert node. This
# turns the manual "download + edit nodes.json + restart" dance into an API:
# paste a Hugging Face .gguf URL, Twhyne downloads it, appends a registry
# entry, and registers the node live - the same way a RAG dataset is added.
import threading as _threading
import urllib.request as _urlreq
import urllib.parse as _urlparse

_MODEL_JOBS = {}          # job_id -> {state, pct, msg, node_id}
_MODEL_JOBS_LOCK = _threading.Lock()


def _job_set(job_id, **kw):
    with _MODEL_JOBS_LOCK:
        _MODEL_JOBS.setdefault(job_id, {}).update(kw)


def _valid_gguf_url(url):
    try:
        u = _urlparse.urlparse(url)
    except Exception:
        return False
    # Only https, only Hugging Face hosts, only .gguf files. Keeps this from
    # becoming an arbitrary-URL fetcher (SSRF) - it is a model importer.
    host = (u.hostname or '').lower()
    ok_host = host == 'huggingface.co' or host.endswith('.huggingface.co') or host.endswith('.hf.co')
    return u.scheme == 'https' and ok_host and u.path.lower().endswith('.gguf')


def _download_gguf(url, dest, job_id):
    tmp = dest.with_suffix('.part')
    try:
        req = _urlreq.Request(url, headers={'User-Agent': 'twhyne-model-importer'})
        with _urlreq.urlopen(req, timeout=60) as r:
            total = int(r.headers.get('Content-Length', 0))
            done = 0
            with open(tmp, 'wb') as f:
                while True:
                    chunk = r.read(1 << 20)  # 1 MiB
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        _job_set(job_id, pct=round(100 * done / total, 1))
        tmp.rename(dest)
        return True, None
    except Exception as e:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return False, str(e)


def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization"]}}, supports_credentials=False)

    node_registry = NodeRegistry()
    models_dir = Path(__file__).parent.parent / 'models'
    # Runtime (not import-time) code-model selection: by now the models
    # volume is mounted, so the choice reflects what is actually on disk.
    _select_code_model()

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
        lambda: CodeNode(node_id=CODE_NODE_ID, name=CODE_NODE_NAME,
                         description='Code generation with execute-before-answer verification',
                         model_path=models_dir / CODE_MODEL_FILE),
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
    # A GGUF plus a registry entry becomes an expert node - no rebuild. Entries
    # can arrive from nodes.json at startup OR the /api/models/add pipeline.
    import json as _json
    registry_file = models_dir / 'nodes.json'
    _BUILTIN_IDS = set(node_registry.get_all_node_ids())

    def _register_entry(entry):
        """Register one registry entry as a live node. Raises on failure."""
        from flux_nodes.custom import CustomLLMNode
        nid = entry.get('node_id', '')
        if nid in _BUILTIN_IDS:
            logger.info(f"Skipping registry entry {nid}: shadows a built-in node")
            return None
        # role "code" gets the full VERIFIED CodeNode pipeline (execute-
        # before-answer, retry, honest labels) instead of raw generation.
        if entry.get('role') == 'code':
            n = CodeNode(node_id=entry['node_id'],
                         name=entry.get('name', entry['node_id']),
                         description=entry.get('description', ''),
                         model_path=models_dir / entry['model_file'])
            n.keywords = entry.get('keywords', [])
        else:
            n = CustomLLMNode(
                node_id=entry['node_id'],
                name=entry.get('name', entry['node_id']),
                description=entry.get('description', ''),
                model_path=models_dir / entry['model_file'],
                keywords=entry.get('keywords', []),
                prompt_template=entry.get('prompt_template'),
                n_ctx=int(entry.get('n_ctx', 4096)),
                max_tokens=int(entry.get('max_tokens', 512)),
                temperature=float(entry.get('temperature', 0.5)))
        node_registry.register_node(n)
        logger.info(f"Registered custom node: {n.name} ({n.node_id})")
        return n

    def _read_registry():
        if not registry_file.exists():
            return []
        try:
            return _json.loads(registry_file.read_text(encoding='utf-8-sig'))
        except Exception as e:
            logger.error(f"nodes.json parse error: {e}")
            return []

    def _write_registry(entries):
        registry_file.write_text(_json.dumps(entries, indent=2), encoding='utf-8')

    for _entry in _read_registry():
        try:
            _register_entry(_entry)
        except Exception as ce:
            logger.error(f"Failed to load custom node {_entry}: {ce}")

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
                    # WHY a node is offline ("model not downloaded - re-run
                    # the launcher"), so the UI explains instead of just
                    # showing a red dot on a deprecated name.
                    'status_detail': getattr(node, 'status_detail', None),
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

        # A chat attachment must actually be READ, not just saved. Images go
        # to the vision node via image_path (existing behavior); documents
        # are ingested into a knowledge base right here so the very next
        # question can retrieve and cite them. Anything we cannot extract
        # text from is refused honestly instead of silently ignored.
        ext = os.path.splitext(file.filename or '')[1].lower()
        image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        if ext in image_exts:
            return jsonify({'filepath': filepath, 'kind': 'image',
                            'message': 'Image attached - it will be analyzed '
                                       'by the vision node.'})
        text = None
        if ext == '.pdf':
            try:
                from pypdf import PdfReader
                text = '\n'.join((pg.extract_text() or '')
                                 for pg in PdfReader(filepath).pages).strip()
            except Exception as e:
                logger.error(f"PDF extraction failed for {file.filename}: {e}")
        else:
            try:
                with open(filepath, 'rb') as f:
                    raw = f.read(5 * 1024 * 1024)
                text = raw.decode('utf-8', errors='ignore').strip()
                # Binary masquerading as text: mostly non-printable -> refuse.
                if text and sum(c.isprintable() or c.isspace()
                                for c in text[:2000]) < 0.8 * len(text[:2000]):
                    text = None
            except Exception as e:
                logger.error(f"Read failed for {file.filename}: {e}")
        if not text:
            return jsonify({'filepath': filepath, 'kind': 'unsupported',
                            'message': f'"{file.filename}" was saved but no '
                                       f'text could be extracted from it, so '
                                       f'answers cannot cite it. Supported: '
                                       f'PDF and plain-text formats (txt, md, '
                                       f'csv, json, code), plus images.'})
        try:
            _set_progress('indexing', f'reading {file.filename}')
            ds = get_rag_manager().create_dataset(
                file.filename, 'Chat attachment', [{
                    'filename': file.filename, 'type': 'text',
                    'content': text, 'encoding': 'utf-8'}],
                progress=lambda d, t: _set_progress(
                    'indexing', f'{file.filename} — section {d}/{t}'))
        except Exception as e:
            logger.error(f"Attachment ingest failed: {e}")
            return jsonify({'error': 'The file was read but could not be '
                                     'indexed. Try the Knowledge Bases '
                                     'panel.'}), 500
        finally:
            _set_progress('idle')
        return jsonify({'filepath': filepath, 'kind': 'document',
                        'dataset_id': ds.get('id'),
                        'chunks': ds.get('document_count'),
                        'message': f'"{file.filename}" was read and indexed '
                                   f'({ds.get("document_count")} sections). '
                                   f'Answers can now retrieve and cite it.'})

    def _dataset_age_days(dataset_id):
        """Age of the dataset in whole days, or None (legacy datasets
        stored a uuid in created_at and have unknowable age)."""
        try:
            from datetime import datetime as _dt
            info = get_rag_manager().datasets.get(dataset_id) or {}
            created = _dt.fromisoformat(str(info.get('created_at')))
            return max(0, (_dt.now() - created).days)
        except Exception:
            return None

    def _retrieve(prompt, dataset_id, role='public'):
        """Semantic retrieval. Returns (context, sources, top_score).

        Context is capped at MAX_CONTEXT_CHARS so the grounded prompt always
        fits inside the model's context window.
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
                results.extend(rm.search_dataset(did, prompt, top_k=8, role=role))
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

    @app.after_request
    def _redact_response(resp):
        # Single choke point: every /query answer passes through here,
        # including cached and error paths, so the veto cannot be bypassed
        # by a code path that forgot to call it.
        try:
            if request.path == '/query' and resp.is_json:
                data = resp.get_json(silent=True) or {}
                changed = False
                for k in ('result', 'response'):
                    if isinstance(data.get(k), str):
                        scrubbed, hits = _scrub_secrets(data[k])
                        if hits:
                            data[k] = scrubbed
                            changed = True
                if changed:
                    data['redacted'] = True
                    logger.warning("Output secret veto redacted content from a response")
                    resp.set_data(__import__('json').dumps(data))
                    _escalate_alert({
                        'severity': 'high', 'type': 'output-redaction',
                        'what': f"Output redaction fired for role "
                                f"'{data.get('role')}'.",
                        'why': 'A response contained a value matching a secret '
                               'pattern and was scrubbed before returning. Review '
                               'whether the query tried to elicit a credential.',
                        'subject': data.get('role'),
                    })
                # One tamper-evident audit record per answered query.
                resp_low = (data.get('response') or '').lower() if isinstance(
                    data.get('response'), str) else ''
                verdict = ('refused' if resp_low
                           and ('do not have' in resp_low
                                or 'not in the' in resp_low
                                or 'not authorized' in resp_low)
                           else 'cancelled' if data.get('cancelled')
                           else 'answered')
                # SENSITIVE-REQUEST VERDICTS: asking for a password, key,
                # salary or credential is a security-relevant event even when
                # the answer is a polite "the sources don't provide that".
                # The audit must record it as a refusal of a sensitive
                # request, not ordinary source absence - the distinction is
                # what lets an operator spot probing.
                prompt_low = (request.get_json(silent=True) or {}).get(
                    'prompt', '').lower()
                sensitive_ask = bool(re.search(
                    r'\b(password|passphrase|salar(y|ies)|api[ _-]?key|secret|'
                    r'credential|access[ _-]?token|private[ _-]?key|ssn|'
                    r'social security)\b', prompt_low))
                if sensitive_ask and verdict == 'answered' and resp_low and (
                        re.search(r"do(es)?\s*(not|n't)\s*(provide|contain|"
                                  r"include|state|specify|mention)", resp_low)
                        or 'not available' in resp_low
                        or "don't have" in resp_low):
                    verdict = 'refused'
                # VERIFICATION GATES: every answer carries a machine-readable
                # record of each control it passed through. Stamped here at
                # the choke point so no code path can produce an answer
                # without a gate record; the same block is chained into the
                # audit ledger. This is the structured form of the trust
                # labels ("how was this answer earned").
                node = str(data.get('node_id') or '')
                req_body = request.get_json(silent=True) or {}
                how = ('computed' if node.startswith('math') else
                       'extracted' if data.get('extractive') else
                       'cited' if data.get('grounded') else
                       'executed' if node.startswith(('code', 'verified')) else
                       'generated')
                gates = {
                    'identity': {'role': data.get('role') or req_body.get('role', 'public'),
                                 'signed': bool(getattr(__import__('flask').g,
                                                        'role_signed', False))},
                    'permission': {'enforced': True,
                                   'denied_sources': int(data.get('denied_sources') or 0)},
                    'retrieval': {'grounded': bool(data.get('grounded')),
                                  'top_score': data.get('top_score'),
                                  'sources_cited': len(data.get('sources') or []),
                                  'passes': int(data.get('retrieval_passes') or
                                                (1 if data.get('grounded') else 0))},
                    'generation': how,
                    # Temporal self-report: answered when, from data how old.
                    # A system without a clock cannot state staleness; the
                    # orchestrator can, so every grounded answer discloses it.
                    'time': {'answered_at': __import__('datetime').datetime
                             .now().isoformat(timespec='seconds'),
                             'dataset_age_days': data.get('dataset_age_days')},
                    'redaction': 'fired' if data.get('redacted') else 'clean',
                    'verdict': verdict,
                    'sensitive_request': sensitive_ask,
                    'verdict_reason': ('sensitive request - not authorized or '
                                       'not in authorized sources'
                                       if sensitive_ask and verdict == 'refused'
                                       else None),
                    'cached': bool(data.get('cached')),
                }
                data['gates'] = gates
                resp.set_data(__import__('json').dumps(data))
                _audit_append({
                    'role': data.get('role'),
                    'prompt': req_body.get('prompt', ''),
                    'node_id': data.get('node_id'),
                    'sources': data.get('sources'),
                    'verdict': verdict,
                    'redacted': data.get('redacted'),
                    'cached': data.get('cached'),
                    'gates': gates,
                    'evidence': data.get('evidence'),
                })
        except Exception as e:
            logger.error(f"Redaction/audit hook error: {e}")
        return resp

    _TIME_Q_RE = re.compile(
        r"^\s*(what('?s| is) (the )?(time|date|current (time|date)|today'?s date)|"
        r"what day is (it|today)|what time is it)\b", re.I)
    _TIMER_Q_RE = re.compile(
        r"\b(set|start|run|create)\s+(a\s+)?(timer|alarm|reminder|countdown)\b|"
        r"\bremind me\b|\bwake me\b|\bin \d+\s*(min|minute|hour|second|sec)", re.I)
    _SUMMARIZE_RE = re.compile(
        r"\b(summari[sz]e|key points|main points|overview of|tl;?dr|"
        r"what (is|are) (this|the) (doc|document|pdf|file)s? about|"
        r"gist of)\b", re.I)

    @app.route('/query', methods=['POST', 'OPTIONS'])
    def submit_query():
        if request.method == 'OPTIONS':
            return '', 200
        blocked, lic_msg = _license_blocked()
        if blocked:
            return jsonify({'error': lic_msg, 'license_invalid': True}), 403
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            prompt = data.get('prompt', '')

            # CLOCK: a model has no persistent existence between calls and
            # therefore no clock; asking it the time yields training-data
            # hallucination. The orchestrator IS a persistent process, so
            # time questions are answered deterministically here - the same
            # reasoning that sends arithmetic to SymPy, applied to time.
            _role = str(data.get('role', 'public') or 'public').strip().lower()
            if _TIME_Q_RE.match(prompt or ''):
                from datetime import datetime as _dt
                now = _dt.now()
                text = now.strftime('%A, %B %d, %Y, %H:%M %Z').strip().rstrip(',') \
                       + ' (local system time)'
                return jsonify({'result': text, 'response': text,
                                'node_id': 'clock', 'sources': [],
                                'grounded': False, 'role': _role})
            # Timer / reminder: handled by the tool/action policy engine
            # (layer 9 v0.1). A user-requested timer is NOT unprompted action
            # - consent happens at request time - so it is created under the
            # whitelisted `timer.notify` capability (role-checked, duration-
            # and count-bounded, audited) and FIRES AT READ TIME: its state
            # is computed from the clock whenever the timer list is observed.
            # The system never notifies or acts on its own between reads.
            # ANY mention of timers that is not a creation request routes to
            # deterministic timer state - never to the language model. The
            # model has no knowledge of timers and will confidently deny
            # they exist ("I didn't set a timer"), contradicting the
            # system's own audited state - the exact hallucination class the
            # kernel exists to prevent. Checking timers IS the firing
            # mechanism (read-time): observing recomputes state from the
            # clock.
            # SCOPE GUARD: none of this applies when the user is TALKING
            # ABOUT timers rather than USING them - "write a countdown timer
            # in Python" is a code request and must reach the code node. An
            # explicit node selection or code/build vocabulary wins.
            _timer_scope = (
                not data.get('node_id')
                and not re.search(
                    r"\b(write|implement|build|make|code|coding|function|"
                    r"program|script|python|javascript|java|class|app|"
                    r"component|explain|example)\b", prompt or '', re.I))
            if (_timer_scope
                    and re.search(r"\b(timer|timers|reminder|reminders|"
                                  r"countdown|alarm)\b", prompt or '', re.I)
                    and not _TIMER_Q_RE.search(prompt or '')):
                from identity import resolve_identity as _ri
                _subj, _role, _sig, _iderr = _ri(request, data)
                if _iderr:
                    return jsonify({'error': _iderr,
                                    'identity_required': True}), 401
                tl = _timers_observe(_role, _subj)
                if not tl:
                    text = "You have no timers."
                else:
                    from datetime import datetime as _dt
                    now = time.time()
                    lines, any_elapsed = [], False
                    for t in tl[:10]:
                        if t['status'] == 'pending':
                            rem = max(0, int(t['due_at'] - now))
                            lines.append(f"- {t['label'] or t['id']}: "
                                         f"{rem // 60}m {rem % 60}s remaining")
                        else:
                            if t['status'] == 'elapsed':
                                any_elapsed = True
                                due = _dt.fromtimestamp(
                                    t['due_at']).strftime('%H:%M:%S')
                                lines.append(f"- {t['label'] or t['id']}: "
                                             f"ELAPSED (was due {due})")
                            else:
                                lines.append(f"- {t['label'] or t['id']}: "
                                             f"{t['status'].upper()}")
                    text = ("Your timers (state computed from the clock as "
                            "you asked - read-time firing):\n"
                            + "\n".join(lines))
                    if any_elapsed:
                        text += ("\nTwhyne does not push notifications: a "
                                 "timer's state is computed when it is "
                                 "observed - by you asking, or by the app "
                                 "polling the timer list on your behalf.")
                return jsonify({'result': text, 'response': text,
                                'node_id': 'action-policy', 'sources': [],
                                'grounded': False, 'role': _role,
                                'timers': tl,
                                'gates': {'verdict': 'answered',
                                          'action': 'timer.notify'}})
            if _timer_scope and _TIMER_Q_RE.search(prompt or ''):
                m = re.search(r"(\d+(?:\.\d+)?)\s*(hour|hr|minute|min|second|sec)",
                              prompt, re.I)
                if not m:
                    text = ("I can set a governed timer, but I need a "
                            "duration - e.g. \"set a timer for 10 minutes\". "
                            "Note how Twhyne timers work: they fire at read "
                            "time (when you or the app next checks the timer "
                            "list), never as an unprompted action.")
                    return jsonify({'result': text, 'response': text,
                                    'node_id': 'action-policy', 'sources': [],
                                    'grounded': False, 'role': _role,
                                    'gates': {'verdict': 'refused',
                                              'verdict_reason':
                                              'timer requested without a '
                                              'parseable duration'}})
                mult = {'h': 3600, 'm': 60, 's': 1}[m.group(2)[0].lower()]
                secs = float(m.group(1)) * mult
                # An ACTION uses the authoritative identity: signed subject +
                # role, never a bare body assertion the token contradicts.
                from identity import resolve_identity as _ri
                _subj, _role, _sig, _iderr = _ri(request, data)
                if _iderr:
                    return jsonify({'error': _iderr,
                                    'identity_required': True}), 401
                # DERIVED label, never the raw prompt: labels are echoed back
                # into chat and chat re-enters LLM prompts via history, so a
                # raw prompt stored here is a stored-injection channel.
                _lbl = f"{m.group(1)} {m.group(2).lower()} timer"
                timer, err = _timer_create(_role, secs, label=_lbl,
                                           subject=_subj)
                if err:
                    _status, msg = err
                    text = f"Timer refused by the action policy: {msg}"
                    return jsonify({'result': text, 'response': text,
                                    'node_id': 'action-policy', 'sources': [],
                                    'grounded': False, 'role': _role,
                                    'gates': {'verdict': 'refused',
                                              'verdict_reason': msg}})
                from datetime import datetime as _dt
                due = _dt.fromtimestamp(timer['due_at']).strftime('%H:%M:%S')
                text = (f"Timer set for {m.group(1)} {m.group(2)}(s), due at "
                        f"{due} (id {timer['id']}). Honest mechanics: this "
                        f"timer fires at read time - it will show as elapsed "
                        f"the next time the timer list is checked, and Twhyne "
                        f"takes no action on its own in between. Creation is "
                        f"recorded in the audit ledger under the "
                        f"'timer.notify' action policy.")
                return jsonify({'result': text, 'response': text,
                                'node_id': 'action-policy', 'sources': [],
                                'grounded': False, 'role': _role,
                                'timer': timer,
                                'gates': {'verdict': 'answered',
                                          'action': 'timer.notify'}})
            node_id = data.get('node_id')
            conversation_history = data.get('conversation_history', [])
            if len(conversation_history) > 10:
                conversation_history = conversation_history[-5:]
            if not prompt or not prompt.strip():
                return jsonify({'error': 'No prompt provided'}), 400
            client_rid = str(data.get('client_request_id', '') or '').strip()
            # Role drives permission-before-retrieval: unauthorized documents
            # never enter the candidate set. Default 'public' = least access.
            # SIGNED IDENTITY: a valid Bearer token's role is authoritative and
            # cannot be overridden by the request body; without a token the
            # role falls back to 'public' (or a body-asserted role only when
            # signed identity is not required - preserves the dev workflow).
            from identity import resolve_role
            from flask import g as _g
            role, role_signed, id_err = resolve_role(request, data)
            _g.role_signed = role_signed
            if id_err:
                return jsonify({'error': id_err, 'identity_required': True}), 401
            _set_progress('routing')

            from flux_nodes.base import Query

            # ---- DETERMINISTIC TOOLS FIRST -------------------------------
            # Math is exact and instant (SymPy). It must short-circuit BEFORE
            # retrieval so "2+2" never gets swept into the slow grounded path
            # just because a document chunk happens to score above threshold.
            if _looks_like_math(prompt):
                math_node = node_registry.get_node('math-llm-eval')
                if (math_node and math_node.is_available
                        and get_rag_manager().node_can_access('math-llm-eval', role)):
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
                                 dataset_id or '*', role, get_rag_manager().version())
                    hit = _ANSWER_CACHE.get(cache_key)
                    if hit:
                        logger.info("Answer cache hit")
                        # Honest labeling: a cached answer must be
                        # distinguishable from a fresh one ("+cached"
                        # suffix), not silently identical.
                        return jsonify({**hit, 'cached': True,
                                        'node_id': hit.get('node_id', '') + '+cached'})
                except Exception:
                    cache_key = None

            _set_progress('retrieving documents')
            context, sources, top_score, kept = _retrieve(prompt, dataset_id, role)
            retrieval_passes = 1 if kept else 0

            # BOUNDED ITERATIVE RETRIEVAL: one deterministic refinement pass.
            # Sufficiency is measured, not model-graded: if most of the
            # question's content words are absent from the retrieved text,
            # re-query emphasizing the missing terms and merge new chunks.
            # Exactly one extra pass - never a loop.
            if forced and kept:
                pw = {w for w in re.findall(r'[a-z0-9]+', prompt.lower())
                      if len(w) > 3 and w not in _STOP_LITE}
                text_all = ' '.join(r.get('content', '') for r in kept).lower()
                missing = [w for w in pw if w not in text_all]
                if pw and len(missing) / len(pw) > 0.5:
                    refined = ' '.join(missing + sorted(pw)[:4])
                    logger.info(f"Iterative retrieval pass 2 (coverage "
                                f"{1 - len(missing)/len(pw):.0%}): {refined[:80]}")
                    _c2, _s2, _t2, k2 = _retrieve(refined, dataset_id, role)
                    seen = {(r.get('source'), r.get('chunk_index')) for r in kept}
                    extra = [r for r in k2
                             if (r.get('source'), r.get('chunk_index')) not in seen]
                    if extra:
                        kept = kept + extra[:3]
                        retrieval_passes = 2
                        context = ""
                        sources = []
                        for r in kept:
                            piece = f"[Source: {r['source']}]\n{r['content']}\n\n"
                            if len(context) + len(piece) > MAX_CONTEXT_CHARS:
                                break
                            context += piece
                            if r['source'] not in sources:
                                sources.append(r['source'])
            thr = GROUND_THRESHOLD if forced else GROUND_THRESHOLD_AUTO
            should_ground = forced or (bool(context) and top_score >= thr)

            # SUMMARIZE / OVERVIEW: structurally unanswerable by retrieval -
            # "summarize the key points" resembles no chunk, so search comes
            # back empty and the system refuses while holding the whole
            # document. The right context for an overview question is the
            # document itself, in order, under the same permission boundary.
            overview_mode = False
            if (_SUMMARIZE_RE.search(prompt or '')
                    and (not should_ground or top_score < thr)):
                ds_name, ov = get_rag_manager().overview_chunks(
                    dataset_id, role, max_chunks=10)
                if ov:
                    overview_mode = True
                    kept = [{'source': d.get('source'),
                             'content': d.get('content'),
                             'chunk_index': d.get('chunk_index'),
                             'score': 1.0} for d in ov]
                    context, sources = "", []
                    for r in kept:
                        piece = f"[Source: {r['source']}]\n{r['content']}\n\n"
                        if len(context) + len(piece) > MAX_CONTEXT_CHARS:
                            break
                        context += piece
                        if r['source'] not in sources:
                            sources.append(r['source'])
                    top_score = 1.0
                    should_ground = True
                    logger.info(f"Overview mode: summarizing '{ds_name}' "
                                f"({len(kept)} chunks in document order)")

            # Lexical veto for AUTO-grounding: BGE's cosine floor on some
            # corpora sits above the threshold ("reverse a binary tree"
            # scored 0.657 against a Taco Bell 10-K). A genuinely relevant
            # chunk shares at least one meaningful word with the question;
            # a pure embedding-floor artifact shares none.
            if should_ground and not forced and not overview_mode and kept:
                pwords = {w for w in re.findall(r'[a-z0-9]+', prompt.lower())
                          if len(w) > 3 and w not in _STOP_LITE}
                top_text = kept[0].get('content', '').lower()
                hits = sum(1 for w in pwords if w in top_text)
                # Two overlapping words required (when the question has that
                # many): one shared word let a brand-color PDF ground "mixing
                # blue and yellow paint" just because it mentioned "yellow".
                need = min(2, len(pwords))
                if pwords and hits < need:
                    logger.info("Auto-grounding vetoed: insufficient lexical overlap with top chunk")
                    should_ground = False

            if forced and not context:
                # Distinguish two cases the user must be able to tell apart:
                #   no source exists           -> "not in my provided sources"
                #   sources exist, role denied -> "not authorized for this role"
                # Collapsing them makes a permission denial look like a
                # knowledge gap (and turns misconfiguration into silence).
                denied = []
                try:
                    if dataset_id:
                        denied = get_rag_manager().denied_sources(
                            dataset_id, role, query=prompt)
                except Exception:
                    denied = []
                if denied:
                    msg = (f"I'm not authorized to access the sources for this "
                           f"under your role ('{role}'). "
                           f"{len(denied)} source(s) in this dataset are outside "
                           f"this role's permissions.")
                else:
                    msg = "I don't have that in my provided sources."
                return jsonify({'result': msg, 'response': msg,
                                'node_id': 'language-mistral-7b', 'sources': [],
                                'denied_sources': len(denied)})

            # NAMED-SOURCE PREFERENCE: "according to the operations manual"
            # names a document; answering from a different one is a citation
            # failure even when the fact is right. Match the named phrase
            # against retrieved source names (word/prefix overlap so
            # "operations manual" finds twhyne_ops_manual) and, when a match
            # was actually retrieved, restrict the working set to it.
            if should_ground and kept:
                m_named = re.search(
                    r'\baccording to (?:the )?([a-z0-9 _\-]{3,40}?)[,.?]', prompt.lower() + '.')
                if m_named:
                    _ALIASES = {'operations': 'ops', 'documentation': 'docs',
                                'specification': 'spec', 'configuration': 'config'}
                    phrase_words = [w for w in re.findall(r'[a-z0-9]+', m_named.group(1))
                                    if w not in ('the', 'a', 'an', 'of', 'most', 'recent',
                                                 'current', 'latest', 'new')]
                    def _src_score(src):
                        sw = re.findall(r'[a-z0-9]+', src.lower())
                        n = 0
                        for pw in phrase_words:
                            cands = {pw, _ALIASES.get(pw, pw)}
                            if any(c == w or c.startswith(w) or w.startswith(c)
                                   for w in sw if len(w) > 2
                                   for c in cands if len(c) > 2):
                                n += 1
                        return n
                    ranked = sorted({r.get('source', '') for r in kept},
                                    key=_src_score, reverse=True)
                    if ranked and _src_score(ranked[0]) >= 2:
                        preferred = ranked[0]
                        narrowed = [r for r in kept if r.get('source') == preferred]
                        if narrowed:
                            logger.info(f"Named-source preference: '{preferred}'")
                            kept = narrowed
                            sources = [preferred]
                            context = "".join(
                                f"[Source: {r['source']}]\n{r['content']}\n\n"
                                for r in kept)[:MAX_CONTEXT_CHARS]

            if should_ground and context:
                # EXTRACTIVE FAST PATH: for a direct fact question with high
                # retrieval confidence, quote the exact source sentence and
                # skip the LLM entirely - sub-second and more pristine than a
                # paraphrase (the answer is a literal, checkable span).
                ext = _extractive_answer(prompt, kept, top_score)
                if ext:
                    text, _src, _span = ext
                    logger.info(f"Extractive answer (top_score={top_score}, no LLM)")
                    # Source minimality: the answer is one quoted span, so
                    # cite ONLY the document it came from - listing every
                    # retrieved document is decorative and misleading.
                    sources = [_src] if _src else sources[:1]
                    if sources:
                        text += "\n\n---\nSources: " + ", ".join(sources)
                    payload = {'result': text, 'response': text,
                               'node_id': 'rag-extractive', 'sources': sources,
                               'grounded': True, 'top_score': top_score,
                               'extractive': True, 'role': role,
                               'retrieval_passes': retrieval_passes,
                               'dataset_age_days': _dataset_age_days(dataset_id),
                               'evidence': _evidence_records(
                                   [r for r in kept if r.get('source') == _src] or kept,
                                   span=_span, span_source=_src)}
                    if cache_key:
                        _cache_put(cache_key, payload)
                    return jsonify(payload)

                logger.info(f"Grounded answer (top_score={top_score}). Sources: {sources}")
                lang = node_registry.get_node('language-mistral-7b')
                recent = _recent_context(conversation_history)
                hist_block = (f"Recent conversation (for reference only):\n{recent}\n\n"
                              if recent else "")
                from datetime import datetime as _dt
                grounded = (
                    f"Current date: {_dt.now().strftime('%Y-%m-%d')}.\n"
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
                # No decorative citations: if an AUTO-grounded answer admits
                # the sources don't actually contain the information, citing
                # them anyway misleads ("green ... Sources: Wendys-2021.pdf").
                if (not forced and re.search(
                        r"sources\s+do(es)?\s*(not|n't)\s*(directly\s+)?"
                        r"(contain|provide|include|specify|state|mention)",
                        text, re.I)):
                    sources = []
                # SOURCE MINIMALITY: cite what actually supports the answer,
                # not everything retrieval considered. If the model names its
                # sources in the text, the citation list is exactly those;
                # otherwise fall back to the top retrieved document. "Correct
                # answer + four decorative citations" is slop.
                if sources:
                    named_in_text = [s for s in sources
                                     if re.search(re.escape(s), text, re.I)]
                    sources = named_in_text if named_in_text else sources[:1]
                if sources:
                    text += "\n\n---\nSources: " + ", ".join(sources)
                payload = {'result': text, 'response': text,
                           'node_id': 'language-mistral-7b', 'sources': sources,
                           'grounded': True, 'top_score': top_score, 'role': role,
                           'retrieval_passes': retrieval_passes,
                           'dataset_age_days': _dataset_age_days(dataset_id),
                           'evidence': _evidence_records(
                               [r for r in kept if r.get('source') in sources] or kept)}
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

            # NODE-LEVEL PERMISSION: a role may be barred from an expert node
            # (e.g. an imported model trained on confidential data, or a tool
            # node) just as it can be barred from a document. Checked after
            # routing so the refusal names the node the role can't reach.
            if not get_rag_manager().node_can_access(node.node_id, role):
                msg = (f"Your role ('{role}') is not permitted to use the "
                       f"'{node.node_id}' node.")
                return jsonify({'result': msg, 'response': msg,
                                'node_id': node.node_id, 'sources': [],
                                'grounded': False, 'node_denied': True}), 200

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

    # ---- Model pipeline API: add a HF model as a node, like a RAG dataset --
    @app.route('/api/models', methods=['GET'])
    def list_models():
        """All expert nodes, flagging which are user-added (removable)."""
        node_roles = get_rag_manager().get_permissions().get('node_roles') or {}
        out = []
        for node in node_registry.get_all_nodes():
            rule = node_roles.get(node.node_id) or {}
            out.append({'node_id': node.node_id, 'name': node.name,
                        'description': node.description,
                        'builtin': node.node_id in _BUILTIN_IDS,
                        'keywords': list(getattr(node, 'keywords', []) or []),
                        'allowed_roles': rule.get('allowed_roles')})
        return jsonify({'models': out})

    @app.route('/api/models/jobs', methods=['GET'])
    def model_jobs():
        with _MODEL_JOBS_LOCK:
            return jsonify({'jobs': dict(_MODEL_JOBS)})

    @app.route('/api/models/add', methods=['POST', 'OPTIONS'])
    def add_model():
        """Import a Hugging Face GGUF as a live expert node.

        Body: { url, node_id, name?, description?, role?, keywords?,
                prompt_template?, n_ctx?, max_tokens?, temperature? }
        Downloads in the background; poll /api/models/jobs for progress.
        The node registers itself live on completion - no restart.
        """
        if request.method == 'OPTIONS':
            return '', 200
        # Adding a node changes what intelligence runs in the deployment -
        # admin-gated when a token is configured (open on fresh local installs).
        deny = _require_admin()
        if deny:
            return deny
        data = request.get_json() or {}
        url = (data.get('url') or '').strip()
        node_id = (data.get('node_id') or '').strip()
        if not _valid_gguf_url(url):
            return jsonify({'error': 'url must be an https Hugging Face .gguf link'}), 400
        if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{1,63}', node_id or ''):
            return jsonify({'error': 'node_id must be lowercase letters, digits, . _ -'}), 400
        if node_id in _BUILTIN_IDS:
            return jsonify({'error': f'{node_id} shadows a built-in node; choose another id'}), 400

        fname = f"{node_id}.gguf"
        dest = models_dir / fname
        entry = {
            'node_id': node_id,
            'name': data.get('name') or node_id,
            'description': data.get('description', ''),
            'model_file': fname,
            'keywords': data.get('keywords') or [],
            'role': data.get('role'),
            'prompt_template': data.get('prompt_template'),
            'n_ctx': int(data.get('n_ctx', 4096)),
            'max_tokens': int(data.get('max_tokens', 512)),
            'temperature': float(data.get('temperature', 0.5)),
        }
        entry = {k: v for k, v in entry.items() if v is not None}

        # Import-time node ACL: if allowed_roles is given, write it into the
        # policy's node_roles now, so an imported model is governed from the
        # moment it goes live (never a window where it is open to everyone).
        allowed_roles = data.get('allowed_roles')
        if allowed_roles:
            try:
                rm = get_rag_manager()
                pol = dict(rm.get_permissions())
                nr = dict(pol.get('node_roles') or {})
                nr[node_id] = {'allowed_roles': [str(r).strip().lower()
                                                 for r in allowed_roles]}
                pol['node_roles'] = nr
                rm.set_permissions(pol)
            except Exception as e:
                logger.error(f"could not set import-time node roles: {e}")

        job_id = f"add-{node_id}-{int(time.time())}"
        _job_set(job_id, state='downloading', pct=0.0, node_id=node_id,
                 msg='downloading model')

        def _worker():
            if dest.exists():
                ok, err = True, None
                _job_set(job_id, pct=100.0, msg='already downloaded')
            else:
                ok, err = _download_gguf(url, dest, job_id)
            if not ok:
                _job_set(job_id, state='error', msg=f'download failed: {err}')
                return
            _job_set(job_id, state='registering', msg='registering node')
            try:
                _register_entry(entry)
                entries = [e for e in _read_registry() if e.get('node_id') != node_id]
                entries.append(entry)
                _write_registry(entries)
                _job_set(job_id, state='ready', pct=100.0, msg='node is live')
            except Exception as e:
                _job_set(job_id, state='error', msg=f'registration failed: {e}')

        _threading.Thread(target=_worker, daemon=True).start()
        return jsonify({'job_id': job_id, 'node_id': node_id,
                        'poll': '/api/models/jobs'}), 202

    @app.route('/api/models/<node_id>/roles', methods=['GET', 'PUT', 'DELETE'])
    def node_roles_crud(node_id):
        """Read / set / clear the allowed_roles for one node (admin-gated).

        PUT  body {allowed_roles: [...]}  -> only those roles may invoke it.
        DELETE                            -> remove the rule (node follows the
                                             node_default_allowed default).
        Lets an operator adjust node permissions after import without editing
        the whole policy document.
        """
        rm = get_rag_manager()
        if request.method == 'GET':
            rule = (rm.get_permissions().get('node_roles') or {}).get(node_id)
            return jsonify({'node_id': node_id,
                            'allowed_roles': (rule or {}).get('allowed_roles'),
                            'default_allowed': bool(
                                rm.get_permissions().get('node_default_allowed', True))})
        deny = _require_admin()
        if deny:
            return deny
        pol = dict(rm.get_permissions())
        nr = dict(pol.get('node_roles') or {})
        if request.method == 'DELETE':
            nr.pop(node_id, None)
        else:
            roles = (request.get_json(silent=True) or {}).get('allowed_roles')
            if not isinstance(roles, list) or not roles:
                return jsonify({'error': 'allowed_roles must be a non-empty list'}), 400
            nr[node_id] = {'allowed_roles': [str(r).strip().lower() for r in roles]}
        pol['node_roles'] = nr
        rm.set_permissions(pol)
        return jsonify({'success': True, 'node_id': node_id,
                        'allowed_roles': nr.get(node_id, {}).get('allowed_roles')})

    @app.route('/api/models/<node_id>', methods=['DELETE'])
    def delete_model(node_id):
        """Remove a user-added node (built-ins are protected)."""
        deny = _require_admin()
        if deny:
            return deny
        if node_id in _BUILTIN_IDS:
            return jsonify({'error': 'cannot remove a built-in node'}), 400
        node_registry._nodes.pop(node_id, None)
        entries = [e for e in _read_registry() if e.get('node_id') != node_id]
        _write_registry(entries)
        logger.info(f"Removed custom node: {node_id}")
        return jsonify({'removed': node_id})

    @app.route('/api/audit', methods=['GET'])
    def audit_tail():
        """Recent audit records (default last 50) + chain-integrity status."""
        import json as _json
        try:
            limit = int(request.args.get('limit', 50))
        except Exception:
            limit = 50
        recs = []
        if _AUDIT_PATH.exists():
            with open(_AUDIT_PATH) as f:
                lines = [l for l in f if l.strip()]
            for l in lines[-limit:]:
                try:
                    recs.append(_json.loads(l))
                except Exception:
                    pass
        ok, count, broken = _audit_verify()
        return jsonify({'records': recs, 'total': count,
                        'chain_intact': ok, 'broken_at': broken})

    @app.route('/api/audit/verify', methods=['GET'])
    def audit_verify():
        """Prove the audit chain has not been tampered with."""
        ok, count, broken = _audit_verify()
        if not ok:
            _escalate_alert({
                'severity': 'high', 'type': 'audit-tamper',
                'what': f'The audit ledger fails verification at record {broken}.',
                'why': 'A broken hash chain means a past record was altered or '
                       'removed. Preserve the file and investigate disk access.',
                'subject': None,
            })
        return jsonify({'chain_intact': ok, 'records': count, 'broken_at': broken})

    @app.route('/api/identity/token', methods=['POST'])
    def identity_token():
        """Issue a signed identity token for a subject+role.

        Gated by TWHYNE_ADMIN_TOKEN when set (only an operator mints
        identities); open on a fresh local install so the first admin can
        bootstrap. Body: {subject, role, ttl_seconds?}.
        """
        from identity import issue_token
        admin_token = os.environ.get('TWHYNE_ADMIN_TOKEN', '').strip()
        if admin_token:
            supplied = request.headers.get('X-Admin-Token', '').strip()
            if not supplied or not _hmac_equal(supplied, admin_token):
                return jsonify({'error': 'Unauthorized'}), 401
        body = request.get_json(silent=True) or {}
        subject = str(body.get('subject') or '').strip()
        role = str(body.get('role') or 'public').strip().lower()
        if not subject:
            return jsonify({'error': 'subject required'}), 400
        try:
            ttl = int(body.get('ttl_seconds') or 43200)
            tok = issue_token(subject, role, ttl_seconds=ttl)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        return jsonify({'token': tok, 'subject': subject, 'role': role,
                        'expires_in': ttl}), 200

    @app.route('/api/identity/whoami', methods=['GET', 'POST'])
    def identity_whoami():
        """Resolve the role the caller's token/headers would be granted."""
        from identity import resolve_role
        body = request.get_json(silent=True) or {}
        role, signed, err = resolve_role(request, body)
        return jsonify({'role': role, 'signed': signed,
                        'error': err}), (401 if err else 200)

    # ---- Timers: the layer-9 v0.1 surface ----------------------------
    @app.route('/api/timers', methods=['GET', 'POST'])
    def timers_collection():
        from identity import resolve_identity
        body = request.get_json(silent=True) or {}
        subject, role, _signed, id_err = resolve_identity(request, body)
        if id_err:
            return jsonify({'error': id_err, 'identity_required': True}), 401
        if request.method == 'GET':
            # Observation IS the trigger: listing recomputes state from the
            # clock and fires anything past due. The system never acts alone.
            return jsonify({'timers': _timers_observe(role, subject),
                            'server_time': time.time()}), 200
        timer, err = _timer_create(role,
                                   body.get('duration_seconds'),
                                   body.get('label', ''),
                                   subject=subject)
        if err:
            status, msg = err
            return jsonify({'error': msg}), status
        return jsonify({'timer': timer,
                        'note': 'Timers fire at read time: the state is '
                                'computed from the clock whenever the list '
                                'is observed. Twhyne takes no action on its '
                                'own between reads.'}), 201

    @app.route('/api/timers/<tid>', methods=['DELETE'])
    def timers_delete(tid):
        from identity import resolve_identity
        body = request.get_json(silent=True) or {}
        subject, role, signed, id_err = resolve_identity(request, body)
        if id_err:
            return jsonify({'error': id_err, 'identity_required': True}), 401
        with _TIMERS_LOCK:
            timers = _timers_load()
            match = next((t for t in timers if t.get('id') == tid), None)
            if not match:
                return jsonify({'error': 'Timer not found'}), 404
            # Owner may cancel; admin override only with a SIGNED admin
            # token - a body-asserted 'admin' cancels nothing.
            if not (_timer_owned(match, role, subject)
                    or (signed and role == 'admin')):
                return jsonify({'error': 'Not your timer'}), 403
            match['status'] = 'cancelled'
            _timers_save(timers)
        _timer_audit('timer-cancelled', match, role)
        return jsonify({'timer': match}), 200

    @app.route('/api/admin/day-review', methods=['GET'])
    def admin_day_review():
        """Governed reflection v0: the system reviews its own day over the
        ledger and reports to a human. READ-ONLY - it summarizes and proposes,
        it changes nothing (consolidation rung one, safest form). Optional
        ?hours=24 window; admin-gated like the rest of /api/admin.
        """
        import json as _json
        from collections import Counter
        admin_token = os.environ.get('TWHYNE_ADMIN_TOKEN', '').strip()
        if admin_token:
            supplied = request.headers.get('X-Admin-Token', '').strip()
            if not supplied or not _hmac_equal(supplied, admin_token):
                return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        try:
            hours = float(request.args.get('hours', 24))
        except Exception:
            hours = 24
        cutoff = time.time() - hours * 3600
        recs = []
        if _AUDIT_PATH.exists():
            with open(_AUDIT_PATH) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = _json.loads(line)
                    except Exception:
                        continue
                    if float(r.get('ts') or 0) >= cutoff:
                        recs.append(r)
        total = len(recs)
        verdicts = Counter((r.get('verdict') or 'answered') for r in recs)
        roles = Counter((r.get('role') or 'public') for r in recs)
        redactions = sum(1 for r in recs if r.get('redacted'))
        cached = sum(1 for r in recs if r.get('cached'))
        # Observations a human should see - stated, never acted on.
        obs = []
        answered = verdicts.get('answered', 0)
        refused = verdicts.get('refused', 0)
        if total and refused / total > 0.4:
            obs.append(f"High refusal share ({refused}/{total}) - either heavy "
                       f"probing or a corpus/permission gap worth reviewing.")
        if redactions:
            obs.append(f"{redactions} output-redaction event(s) - review whether "
                       f"queries were eliciting secrets.")
        ok, count, broken = _audit_verify()
        if not ok:
            obs.append(f"Audit chain broken at record {broken} - investigate.")
        top_role = roles.most_common(1)
        if top_role and total:
            obs.append(f"Most active role: {top_role[0][0]} "
                       f"({top_role[0][1]}/{total} queries).")
        if not total:
            obs.append("No activity in the window.")
        summary = (f"In the last {int(hours)}h: {total} queries "
                   f"({answered} answered, {refused} refused, {redactions} "
                   f"redacted, {cached} from cache). Audit chain "
                   f"{'intact' if ok else 'BROKEN'}.")
        return jsonify({'success': True, 'window_hours': hours,
                        'generated_at': __import__('datetime').datetime.utcnow().isoformat(),
                        'summary': summary,
                        'counts': {'total': total, 'verdicts': dict(verdicts),
                                   'roles': dict(roles), 'redactions': redactions,
                                   'cached': cached},
                        'observations': obs,
                        'note': 'Read-only reflection. Proposes nothing '
                                'executable; a human decides any action.'}), 200

    @app.route('/api/admin/alerts', methods=['GET'])
    def admin_alerts():
        """Suspicious / notable security events derived from the audit ledger.

        Turns raw audit records into typed alerts with a plain-language
        what/why so an operator can review and act. Signals:
          - audit chain broken               (tamper detected)   -> high
          - output redaction fired           (secret scrubbed)   -> high
          - refusal clusters by role         (probing)           -> medium
          - restricted source in a response  (ACL anomaly)       -> high

        Optional gate: if TWHYNE_ADMIN_TOKEN is set, callers must present a
        matching X-Admin-Token header (the license site forwards
        TWHYNE_BACKEND_ADMIN_TOKEN here). When unset, the endpoint is open —
        it runs on-prem behind the operator's own network.
        """
        import json as _json
        from collections import defaultdict
        admin_token = os.environ.get('TWHYNE_ADMIN_TOKEN', '').strip()
        if admin_token:
            supplied = request.headers.get('X-Admin-Token', '').strip()
            if not supplied or not _hmac_equal(supplied, admin_token):
                return jsonify({'success': False, 'message': 'Unauthorized'}), 401

        try:
            window = int(request.args.get('limit', 2000))
        except Exception:
            window = 2000

        recs = []
        if _AUDIT_PATH.exists():
            with open(_AUDIT_PATH) as f:
                lines = [l for l in f if l.strip()]
            for l in lines[-window:]:
                try:
                    recs.append(_json.loads(l))
                except Exception:
                    pass

        alerts = []

        # 1. Tamper detection — the strongest signal.
        ok, count, broken = _audit_verify()
        if not ok:
            alerts.append({
                'severity': 'high', 'type': 'audit-tamper',
                'what': f'The audit ledger fails verification at record {broken}.',
                'why': 'Each record is hash-chained to the previous one; a broken '
                       'chain means a past record was altered or removed. Preserve '
                       'the file and investigate who has disk access.',
                'subject': None,
            })

        # 2. Redaction events — a secret was caught on the way out.
        redactions = [r for r in recs if r.get('redacted')]
        for r in redactions[-25:]:
            alerts.append({
                'severity': 'high', 'type': 'output-redaction',
                'what': f"Output redaction fired for role '{r.get('role')}' "
                        f"(prompt {r.get('prompt_sha')}).",
                'why': 'The response contained a value matching a secret pattern '
                       'and was scrubbed before returning. Worth reviewing whether '
                       'the query was an attempt to elicit a credential.',
                'subject': r.get('role'),
            })

        # 3. Refusal clusters — repeated denials from one role look like probing.
        refusals = defaultdict(int)
        for r in recs:
            if str(r.get('verdict') or '').upper() == 'REFUSED':
                refusals[r.get('role') or 'unknown'] += 1
        for role, n in refusals.items():
            if n >= 5:
                alerts.append({
                    'severity': 'medium', 'type': 'refusal-cluster',
                    'what': f"Role '{role}' was refused {n} times in the recent window.",
                    'why': 'A run of refusals can be a user repeatedly asking for '
                           'documents or actions outside their permissions — '
                           'consistent with probing. Confirm the role is legitimate.',
                    'subject': role,
                })

        # 4. Restricted source anomaly — a protected doc appeared in a response.
        # Permission-before-retrieval should make this impossible; if it ever
        # shows up it is a first-order ACL bug, so surface it loudly.
        try:
            rmgr = get_rag_manager()
            for r in recs[-200:]:
                role = r.get('role') or 'public'
                for src in (r.get('sources') or []):
                    allowed = rmgr.role_can_access(src, role)
                    if allowed is False:
                        alerts.append({
                            'severity': 'high', 'type': 'acl-anomaly',
                            'what': f"Response to role '{role}' cited '{src}', which "
                                    f"that role is not permitted to access.",
                            'why': 'A restricted source reached an unauthorized role. '
                                   'This should never happen under permission-before-'
                                   'retrieval — treat as an access-control regression.',
                            'subject': src,
                        })
        except Exception:
            pass

        rank = {'high': 0, 'medium': 1, 'low': 2}
        alerts.sort(key=lambda a: rank.get(a.get('severity'), 3))
        # Escalate anything high/medium to the configured person/channel.
        # The per-(type,subject) throttle keeps a repeated scan quiet.
        for a in alerts:
            if a.get('severity') in ('high', 'medium'):
                _escalate_alert(a)
        return jsonify({'success': True, 'alerts': alerts, 'count': len(alerts),
                        'records_scanned': len(recs), 'chain_intact': ok})

    @app.route('/api/permissions', methods=['GET'])
    def get_permissions():
        """The active role-based access policy (roles, per-source rules)."""
        return jsonify(get_rag_manager().get_permissions())

    @app.route('/api/permissions', methods=['POST', 'OPTIONS'])
    def set_permissions():
        """Replace the access policy. Body is the policy document.

        Admin-gated when TWHYNE_ADMIN_TOKEN is set: changing who can see what
        is the most security-critical write in the system, so it must not be
        an anonymous call in a configured deployment. Open on a fresh local
        install so the benchmark and first-run setup still work.
        """
        if request.method == 'OPTIONS':
            return '', 200
        admin_token = os.environ.get('TWHYNE_ADMIN_TOKEN', '').strip()
        if admin_token:
            supplied = request.headers.get('X-Admin-Token', '').strip()
            if not supplied or not _hmac_equal(supplied, admin_token):
                return jsonify({'error': 'Unauthorized - admin token required '
                                'to change the access policy'}), 401
        try:
            get_rag_manager().set_permissions(request.get_json() or {})
            return jsonify({'success': True, 'permissions': get_rag_manager().get_permissions()})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/admin/policy', methods=['GET'])
    def policy_console():
        """Self-contained policy + identity console (no React build needed)."""
        return POLICY_CONSOLE_HTML, 200, {'Content-Type': 'text/html'}

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
            _set_progress('indexing', f'preparing "{name}"')
            try:
                ds = get_rag_manager().create_dataset(
                    name, data.get('description', ''), files,
                    progress=lambda d, t: _set_progress(
                        'indexing', f'"{name}" — section {d}/{t}'))
            finally:
                _set_progress('idle')
            return jsonify({'success': True, 'dataset': ds})
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
    _start_license_heartbeat()
    try:
        # Production WSGI server. A few threads keep /status, /progress and
        # /cancel responsive while the inference lock serializes generation.
        from waitress import serve
        print("Serving with waitress (production WSGI)")
        serve(app, host='0.0.0.0', port=5002, threads=6)
    except ImportError:
        print("waitress not installed; falling back to Flask dev server")
        app.run(host='0.0.0.0', port=5002, debug=False)
