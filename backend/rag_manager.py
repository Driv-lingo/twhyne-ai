#!/usr/bin/env python3
"""RAG Manager with semantic (embedding) retrieval.

Documents and queries are embedded with a small BGE model running on
llama.cpp, and retrieval ranks passages by cosine similarity of MEANING
(not shared words). Falls back to stopword-aware keyword matching if the
embedding model is unavailable, so the system still works either way.
"""

import json
import logging
import math
import os
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).resolve().parent.parent / 'models'
_EMBED_MODEL_FILE = _MODELS_DIR / 'bge-small-en-v1.5-f16.gguf'

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

try:
    import numpy as _np  # ships with llama-cpp-python
except ImportError:
    _np = None

_embed_model = None
_embed_lock = threading.Lock()


def _get_embed_model():
    global _embed_model
    if _embed_model is None and Llama is not None and _EMBED_MODEL_FILE.exists():
        with _embed_lock:
            if _embed_model is None:
                logger.info(f"Loading embedding model: {_EMBED_MODEL_FILE}")
                # n_ctx stays at BGE-small's TRAINING window (512): running
                # past it produces unreliable embeddings (llama.cpp warns
                # "possible training context overflow"). Oversized chunks are
                # truncated in _embed instead of overflowing the window.
                _embed_model = Llama(model_path=str(_EMBED_MODEL_FILE), embedding=True,
                                     n_ctx=512, verbose=False)
                logger.info("Embedding model loaded (semantic retrieval enabled)")
    return _embed_model


def _embed(text: str) -> Optional[List[float]]:
    m = _get_embed_model()
    if m is None:
        return None
    try:
        # SERIALIZED: llama.cpp contexts are not thread-safe, and waitress
        # serves requests on multiple threads - an ingest embedding chunks
        # while a query embeds its retrieval probe crashed the process with
        # a segfault (native code, no traceback, container just dies). Every
        # create_embedding call goes through this lock.
        with _embed_lock:
            # ~1300 chars stays safely under the 512-token training window
            # (PDF text can tokenize near 1 token per 2.5 chars). A truncated
            # embedding of a long chunk beats a corrupted full-window one.
            out = m.create_embedding(text[:1300])
        return out['data'][0]['embedding']
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return None


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


_STOPWORDS = {
    "a", "an", "the", "is", "are", "am", "was", "were", "be", "been", "i", "you", "he",
    "she", "it", "we", "they", "me", "my", "your", "our", "this", "that", "these", "those",
    "to", "for", "of", "in", "on", "at", "by", "with", "from", "as", "and", "or", "but",
    "how", "what", "why", "when", "where", "who", "which", "can", "could", "do", "does",
    "did", "should", "would", "will", "may", "might", "please", "about",
}


def _content_words(text: str) -> set:
    return {w for w in text.lower().split() if w not in _STOPWORDS and len(w) > 1}


# PERMISSION-BEFORE-RETRIEVAL (v1, fail-closed): chunks from documents that
# declare themselves confidential never enter the retrieval candidate set,
# so restricted content cannot be quoted, cited, or leaked into answers.
# (Benchmark: an admin password and a salary were extracted verbatim from a
# document marked "CONFIDENTIAL - RESTRICTED ACCESS".) A future permission
# model can lift this per-session; until then, restricted means excluded.
_RESTRICTED_RE = __import__('re').compile(
    r'\bCONFIDENTIAL\b|\bRESTRICTED\s+ACCESS\b|\bDO\s+NOT\s+DISCLOSE\b', __import__('re').I)
# Chunk-level ACL marker: "[[ROLES: it_admin, admin]]" anywhere in a chunk.
_CHUNK_ROLE_RE = __import__('re').compile(r'\[\[ROLES:\s*([a-z0-9_,\s-]+)\]\]', __import__('re').I)


def _is_restricted(doc) -> bool:
    if 'restricted' not in doc:
        doc['restricted'] = bool(_RESTRICTED_RE.search(doc.get('content', '')))
    return doc['restricted']


# PERMISSION MODEL (v1): authorization is the boundary of retrieval, not a
# post-hoc filter. Each request carries a ROLE; a document is eligible only
# if that role is authorized for its source. Unauthorized documents never
# enter the candidate set - so they cannot be quoted, cited, or leaked, and
# the answer is a clean "not in your authorized sources" refusal.
#
# Policy (rag_storage/permissions.json):
#   {
#     "roles": ["public","staff","nurse","it_admin","admin"],
#     "sources": { "it_confidential": {"allowed_roles": ["it_admin","admin"]} },
#     "restricted_default_roles": ["admin"],   # for CONFIDENTIAL-marked docs
#     "default_allowed": true                  # sources with no rule
#   }
# Matching is by source-name substring so "it_confidential" covers
# "it_confidential.txt". Fail-closed: an unknown role gets only default and
# non-restricted sources.
_DEFAULT_PERMISSIONS = {
    "roles": ["public", "staff", "nurse", "it_admin", "admin"],
    "sources": {},
    "restricted_default_roles": ["admin"],
    "default_allowed": True,
    # VERIFICATION POLICY: what ships when a verifier says no.
    #   on_code_failure: "draft" (default) - ship the best candidate, loudly
    #                    labeled UNVERIFIED with the real error and an
    #                    account of what was tried (a dead-end refusal on a
    #                    reasonable coding question is worse than an honest
    #                    draft);
    #                    "refuse" - broken code never leaves (strict installs).
    # The label is never optional; the knob only picks draft vs refusal.
    "verification": {"on_code_failure": "draft"},
    # ACTION POLICY (layer 9 v0.1): capabilities the system may exercise on a
    # user's prior request. Only notify-style actions exist; each is
    # role-scoped and capped. "*" = any role.
    "actions": {
        "timer.notify": {"allowed_roles": ["*"],
                          "max_duration_hours": 24,
                          "max_pending_per_role": 5}
    },
}


class SemanticRAGManager:
    """Embedding-based retrieval with a keyword fallback."""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or os.environ.get(
            'RAG_STORAGE', str(Path(__file__).resolve().parent / 'rag_storage')))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.datasets_file = self.storage_dir / "datasets.json"
        self.permissions_file = self.storage_dir / "permissions.json"
        self.permissions = self._load_permissions()
        self.datasets = self._load_datasets()
        # Datasets whose embedding backfill already ran this process. Without
        # this, chunks that keep failing to embed were re-attempted on EVERY
        # search - re-embedding thousands of chunks and rewriting the whole
        # datasets.json per query (observed as 600s "general chat" queries).
        self._backfilled = set()
        # Per-dataset normalized embedding matrix, built once and reused.
        # Cosine scoring in pure Python cost seconds per query on large
        # datasets; a cached numpy matrix multiply costs ~2ms.
        self._matrix_cache = {}
        logger.info(f"RAG Manager initialized at {self.storage_dir}")

    def version(self) -> int:
        """Monotonic-ish version of the document store (for answer caches)."""
        try:
            base = int(self.datasets_file.stat().st_mtime)
        except Exception:
            base = 0
        try:
            # Policy changes must also invalidate cached answers, else a
            # revoked role could still be served a cached authorized answer.
            base += int(self.permissions_file.stat().st_mtime)
        except Exception:
            pass
        return base

    # ---- permission model ------------------------------------------------
    def _load_permissions(self) -> Dict[str, Any]:
        if self.permissions_file.exists():
            try:
                p = json.loads(self.permissions_file.read_text(encoding='utf-8-sig'))
                merged = dict(_DEFAULT_PERMISSIONS)
                merged.update(p)
                return merged
            except Exception as e:
                logger.error(f"permissions.json parse error: {e}")
        return dict(_DEFAULT_PERMISSIONS)

    def action_policy(self, action: str) -> Optional[Dict[str, Any]]:
        """Policy for a named action capability, or None if not permitted at
        all. Unknown actions are DENIED by omission (fail-closed)."""
        return (self.permissions.get("actions") or {}).get(action)

    def get_permissions(self) -> Dict[str, Any]:
        return self.permissions

    def set_permissions(self, policy: Dict[str, Any]):
        merged = dict(_DEFAULT_PERMISSIONS)
        merged.update(policy or {})
        self.permissions = merged
        self.permissions_file.write_text(json.dumps(merged, indent=2), encoding='utf-8')
        logger.info("Permissions policy updated")

    def role_can_access(self, source: str, role: str) -> bool:
        """True if *role* is authorized to retrieve documents from *source*."""
        role = (role or 'public').strip().lower()
        pol = self.permissions
        src = (source or '').lower()
        # Explicit per-source rule wins.
        for key, rule in (pol.get('sources') or {}).items():
            if key.lower() in src:
                allowed = [r.lower() for r in (rule.get('allowed_roles') or [])]
                return role in allowed
        return None  # no explicit rule; caller applies content-based default

    def node_can_access(self, node_id: str, role: str) -> bool:
        """True if *role* may invoke expert node *node_id*.

        Mirrors document ACLs for compute nodes: policy 'node_roles' maps a
        node id to its allowed roles. A node with no rule follows
        'node_default_allowed' (default True) so ordinary experts stay open
        while a sensitive node (an imported model over confidential data, a
        tool node) can be locked to specific roles. This is how a customer
        governs WHICH intelligence a role may reach, not just which documents.
        """
        role = (role or 'public').strip().lower()
        nid = (node_id or '').strip()
        rules = self.permissions.get('node_roles') or {}
        rule = rules.get(nid)
        if rule is None:
            # allow an exact-prefix family match, e.g. "code-*"
            for key, r in rules.items():
                if key.endswith('*') and nid.startswith(key[:-1]):
                    rule = r
                    break
        if rule is None:
            return bool(self.permissions.get('node_default_allowed', True))
        allowed = [r.lower() for r in (rule.get('allowed_roles') or [])]
        return role in allowed

    def _chunk_roles(self, doc):
        """CHUNK-LEVEL ACL: an inline '[[ROLES: it_admin, admin]]' tag in a
        chunk restricts THAT chunk to the listed roles, independent of its
        document's rule - so one sensitive paragraph inside an otherwise-open
        file is protected on its own. Parsed once and cached on the chunk."""
        if 'chunk_roles' not in doc:
            m = _CHUNK_ROLE_RE.search(doc.get('content', ''))
            doc['chunk_roles'] = ([r.strip().lower() for r in m.group(1).split(',') if r.strip()]
                                  if m else None)
        return doc['chunk_roles']

    def _doc_allowed(self, doc, role: str) -> bool:
        role = (role or 'public').strip().lower()
        # Chunk-level ACL is the tightest boundary and wins outright.
        chunk_roles = self._chunk_roles(doc)
        if chunk_roles is not None:
            return role in chunk_roles
        source = doc.get('source', '')
        explicit = self.role_can_access(source, role)
        if explicit is not None:
            return explicit
        # No explicit rule: a CONFIDENTIAL-marked document is fail-closed to
        # the restricted_default_roles only; everything else follows
        # default_allowed.
        if _is_restricted(doc):
            allowed = [r.lower() for r in (self.permissions.get('restricted_default_roles') or ['admin'])]
            return role in allowed
        return bool(self.permissions.get('default_allowed', True))

    def _load_datasets(self) -> Dict[str, Any]:
        if self.datasets_file.exists():
            try:
                with open(self.datasets_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading datasets: {e}")
        return {}

    def _save_datasets(self):
        try:
            with open(self.datasets_file, 'w') as f:
                json.dump(self.datasets, f)
        except Exception as e:
            logger.error(f"Error saving datasets: {e}")

    def get_status(self) -> Dict[str, Any]:
        return {"available": True,
                "backend": "semantic_embeddings" if _get_embed_model() else "keyword_fallback",
                "datasets_count": len(self.datasets)}

    def list_datasets(self) -> List[Dict[str, Any]]:
        return [{"id": did, "name": info.get("name", "Unnamed"),
                 "description": info.get("description", ""),
                 "document_count": len(info.get("documents", [])),
                 "is_available": True, "created_at": info.get("created_at", "")}
                for did, info in self.datasets.items()]

    @staticmethod
    def _file_to_text(file_data: Dict[str, Any]) -> str:
        """Extract real text from an uploaded file record ('' if none).

        A PDF is BINARY: decoding its bytes as utf-8 produced garbage
        chunks that embedded to noise and retrieved nothing.
        """
        content = file_data.get("content", "")
        filename = file_data.get("filename", "unknown")
        if file_data.get("encoding") == "base64":
            import base64
            raw = base64.b64decode(content)
            if filename.lower().endswith('.pdf') or raw[:5] == b'%PDF-':
                try:
                    import io
                    from pypdf import PdfReader
                    content = '\n'.join(
                        (pg.extract_text() or '')
                        for pg in PdfReader(io.BytesIO(raw)).pages).strip()
                except Exception as e:
                    logger.error(f"PDF text extraction failed for {filename}: {e}")
                    content = ""
                if not content:
                    logger.error(f"No extractable text in {filename} "
                                 f"(scanned/image-only PDF?)")
            else:
                content = raw.decode('utf-8', errors='ignore')
        return content or ""

    def _ingest_files(self, dataset_id: str, files: List[Dict[str, Any]],
                      start_index: int, progress=None) -> List[Dict[str, Any]]:
        """files -> chunked, embedded document records (shared by create/add)."""
        pending = []  # (filename, chunk_index, text)
        for file_data in files:
            try:
                content = self._file_to_text(file_data)
                if not content:
                    continue
                filename = file_data.get("filename", "unknown")
                # 220 words (~300 tokens) fits comfortably inside the BGE
                # 512-token embedding window; 350-word chunks overflowed it.
                for i, chunk in enumerate(self._chunk_text(content, chunk_size=220)):
                    pending.append((filename, i, chunk))
            except Exception as e:
                logger.error(f"Error processing file: {e}")
        documents = []
        total = len(pending)
        for n, (filename, i, chunk) in enumerate(pending):
            documents.append({"id": f"{dataset_id}-doc-{start_index + len(documents)}",
                              "source": filename, "content": chunk,
                              "chunk_index": i, "embedding": _embed(chunk)})
            if progress and (n % 3 == 0 or n == total - 1):
                try:
                    progress(n + 1, total)
                except Exception:
                    pass
        return documents

    def create_dataset(self, name: str, description: str, files: List[Dict[str, Any]],
                       progress=None) -> Dict[str, Any]:
        """Chunk, embed and index files. `progress(done, total)` is called as
        embedding advances so long ingests can show live status - embedding
        is CPU-bound and a large PDF takes real time.
        """
        dataset_id = f"rag-{uuid.uuid4().hex[:8]}"
        documents = self._ingest_files(dataset_id, files, 0, progress)
        from datetime import datetime as _dt
        self.datasets[dataset_id] = {"name": name, "description": description,
                                     "documents": documents,
                                     # a real timestamp (was a stray uuid), so
                                     # answers can self-report data staleness
                                     "created_at": _dt.now().isoformat(timespec='seconds')}
        self._matrix_cache.pop(dataset_id, None)
        self._save_datasets()
        logger.info(f"Created dataset '{name}' with {len(documents)} chunks")
        return {"id": dataset_id, "name": name, "description": description,
                "document_count": len(documents), "is_available": True}

    def add_files(self, dataset_id: str, files: List[Dict[str, Any]],
                  progress=None) -> Optional[Dict[str, Any]]:
        """Append files to an existing dataset (knowledge bases are editable,
        not create-once). Returns the updated summary, or None if not found.
        """
        if dataset_id not in self.datasets:
            return None
        info = self.datasets[dataset_id]
        docs = info.get("documents", [])
        new_docs = self._ingest_files(dataset_id, files, len(docs), progress)
        docs.extend(new_docs)
        info["documents"] = docs
        self._matrix_cache.pop(dataset_id, None)
        self._backfilled.discard(dataset_id)
        self._save_datasets()
        logger.info(f"Added {len(new_docs)} chunks to dataset "
                    f"'{info.get('name')}'")
        return {"id": dataset_id, "name": info.get("name"),
                "added_chunks": len(new_docs), "document_count": len(docs)}

    def remove_source(self, dataset_id: str, source: str) -> Optional[int]:
        """Remove every chunk of one source file from a dataset. Returns the
        number of chunks removed, or None if the dataset doesn't exist."""
        if dataset_id not in self.datasets:
            return None
        info = self.datasets[dataset_id]
        docs = info.get("documents", [])
        keep = [d for d in docs if (d.get("source") or "") != source]
        removed = len(docs) - len(keep)
        if removed:
            info["documents"] = keep
            self._matrix_cache.pop(dataset_id, None)
            self._save_datasets()
            logger.info(f"Removed {removed} chunks of '{source}' from "
                        f"'{info.get('name')}'")
        return removed

    def all_sources(self) -> set:
        """Every source filename currently present in any dataset - the
        ground truth for 'does this cited document still exist'."""
        out = set()
        for info in self.datasets.values():
            for d in info.get("documents", []):
                if d.get("source"):
                    out.add(d["source"])
        return out

    def dataset_sources(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Distinct source files in a dataset with their chunk counts."""
        info = self.datasets.get(dataset_id) or {}
        counts: Dict[str, int] = {}
        for d in info.get("documents", []):
            s = d.get("source") or "unknown"
            counts[s] = counts.get(s, 0) + 1
        return [{"source": s, "chunks": n} for s, n in sorted(counts.items())]

    def match_dataset(self, prompt: str) -> Optional[str]:
        """Resolve a knowledge base the user named in plain language -
        "tell me about 'twhyne'", "in the handbook database, what..." -
        to its dataset id. TOKEN-based: a KB named "Twhyne Docs" or
        "twhyne_overview.pdf" must match "tell me about twhyne" (exact
        whole-name matching silently failed on any decorated name, and the
        question then fell through to the ungrounded language model, which
        improvises from the name - the worst possible failure).
        None if nothing matches; best token coverage wins.
        """
        pset = set(re.findall(r'[a-z0-9]+', (prompt or "").lower()))
        generic = {'the', 'and', 'for', 'doc', 'docs', 'file', 'files',
                   'data', 'notes', 'new', 'test', 'pdf', 'txt', 'base',
                   'database', 'knowledge'}
        best, best_score = None, 0.0
        for did, info in self.datasets.items():
            toks = [t for t in re.findall(
                r'[a-z0-9]+', str(info.get("name") or "").lower())
                if len(t) >= 3 and t not in generic]
            if not toks:
                continue
            hits = [t for t in toks if t in pset]
            if not hits:
                continue
            # A single-token hit must be distinctive (>=4 chars) so a KB
            # named "hr" or "log" can't be summoned by every sentence.
            if len(hits) == 1 and len(hits[0]) < 4:
                continue
            score = len(hits) / len(toks)
            if score > best_score:
                best, best_score = did, score
        return best

    def delete_dataset(self, dataset_id: str) -> bool:
        if dataset_id in self.datasets:
            del self.datasets[dataset_id]
            self._matrix_cache.pop(dataset_id, None)
            self._save_datasets()
            return True
        return False

    def _ensure_embeddings(self, dataset_id: str):
        """Backfill embeddings for datasets created before semantic search.

        Runs AT MOST ONCE per dataset per process: chunks that still fail to
        embed are left for keyword scoring rather than retried on every
        search (the retry loop made every multi-dataset query take minutes).
        """
        if _get_embed_model() is None or dataset_id in self._backfilled:
            return
        self._backfilled.add(dataset_id)
        docs = self.datasets[dataset_id].get("documents", [])
        missing = [d for d in docs if not d.get("embedding")]
        if not missing:
            return
        logger.info(f"Backfilling embeddings for {len(missing)} chunks (one-time)...")
        fixed = 0
        for d in missing:
            emb = _embed(d["content"])
            if emb:
                d["embedding"] = emb
                fixed += 1
        if fixed:
            self._matrix_cache.pop(dataset_id, None)
            self._save_datasets()
        logger.info(f"Embedding backfill complete ({fixed}/{len(missing)} chunks embedded).")

    def _embedding_matrix(self, dataset_id):
        """(normalized numpy matrix, docs-with-embeddings) for a dataset."""
        docs = self.datasets[dataset_id].get("documents", [])
        cached = self._matrix_cache.get(dataset_id)
        if cached is not None:
            return cached
        # Matrix holds ALL embedded docs; role-based permission filtering
        # happens per-query in search_dataset (a single cached matrix cannot
        # be role-specific).
        embdocs = [d for d in docs if d.get("embedding")]
        if not embdocs or _np is None:
            self._matrix_cache[dataset_id] = (None, embdocs)
            return None, embdocs
        M = _np.asarray([d["embedding"] for d in embdocs], dtype=_np.float32)
        norms = _np.linalg.norm(M, axis=1)
        norms[norms == 0] = 1e-9
        M = M / norms[:, None]
        self._matrix_cache[dataset_id] = (M, embdocs)
        return M, embdocs

    def overview_chunks(self, dataset_id: Optional[str] = None,
                        role: str = "public", max_chunks: int = 10):
        """First authorized chunks of a dataset in document order.

        Summarize/overview questions are structurally unanswerable by
        retrieval - "summarize the key points" resembles no chunk, so
        semantic search returns nothing and the system refuses despite
        having the whole document. The overview context is the document
        itself, in order, behind the same permission boundary as search.
        Returns (dataset_name, chunks) or (None, []).
        """
        ids = [dataset_id] if dataset_id and dataset_id in self.datasets \
            else sorted(self.datasets,
                        key=lambda k: str(self.datasets[k].get('created_at') or ''),
                        reverse=True)
        for did in ids:
            docs = self.datasets[did].get("documents", [])
            allowed = [d for d in sorted(
                docs, key=lambda d: (d.get('source') or '',
                                     d.get('chunk_index') or 0))
                if self._doc_allowed(d, role)]
            if allowed:
                return self.datasets[did].get('name') or did, allowed[:max_chunks]
        return None, []

    def search_dataset(self, dataset_id: str, query: str, top_k: int = 4,
                       role: str = "public") -> List[Dict[str, Any]]:
        if dataset_id not in self.datasets:
            return []
        documents = self.datasets[dataset_id].get("documents", [])

        # Semantic path
        qv = _embed(query)
        if qv is not None:
            self._ensure_embeddings(dataset_id)
            M, embdocs = self._embedding_matrix(dataset_id)
            if M is not None:
                q = _np.asarray(qv, dtype=_np.float32)
                qn = _np.linalg.norm(q)
                q = q / (qn if qn else 1e-9)
                sims = M @ q
                order = _np.argsort(-sims)
                scored = []
                for i in order:
                    d = embdocs[int(i)]
                    # PERMISSION BOUNDARY: a document the role may not access
                    # is skipped before it can become a candidate.
                    if not self._doc_allowed(d, role):
                        continue
                    scored.append((float(sims[int(i)]), d))
                    if len(scored) >= top_k:
                        break
            else:
                ranked = sorted(((_cosine(qv, d["embedding"]), d) for d in embdocs),
                                key=lambda x: x[0], reverse=True)
                scored = [(s, d) for s, d in ranked if self._doc_allowed(d, role)][:top_k]
            return [{"title": d.get("source", ""), "content": d["content"],
                     "score": round(float(s), 3), "source": d.get("source", ""),
                     "chunk_index": d.get("chunk_index", 0)}
                    for s, d in scored]

        # Keyword fallback
        query_words = _content_words(query)
        if not query_words:
            return []
        results = []
        for doc in documents:
            if not self._doc_allowed(doc, role):
                continue
            matching = query_words.intersection(_content_words(doc["content"]))
            if matching:
                score = len(matching) / max(len(query_words), 1)
                results.append({"title": doc.get("source", ""), "content": doc["content"],
                                "score": round(score, 3), "source": doc.get("source", ""),
                                "chunk_index": doc.get("chunk_index", 0)})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def denied_sources(self, dataset_id: str, role: str = "public",
                       query: str = "") -> List[str]:
        """Distinct sources this role may NOT access that look relevant.

        Lets the caller distinguish "nothing relevant exists" from "relevant
        material may exist but this role is not permitted to see it" — two
        cases that must not collapse into the same user-facing answer. When a
        query is given, only denied documents with real lexical overlap count
        as relevant, so an unrelated restricted document does not turn every
        unknown question into a false "not authorized". Returns source names
        only, never content.
        """
        if dataset_id not in self.datasets:
            return []
        qwords = _content_words(query) if query else set()
        need = min(2, len(qwords)) if qwords else 0
        denied = []
        seen_denied = set()
        for doc in self.datasets[dataset_id].get("documents", []):
            src = doc.get("source", "")
            if src in seen_denied or self._doc_allowed(doc, role):
                continue
            if qwords:
                overlap = len(qwords.intersection(_content_words(doc["content"])))
                if overlap < need:
                    continue
            seen_denied.add(src)
            denied.append(src)
        return denied

    def _chunk_text(self, text: str, chunk_size: int = 350, overlap: int = 50) -> List[str]:
        if not text:
            return []
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        chunks = chunks if chunks else [text]
        # HARD CHARACTER CAP. Word-count chunking assumes prose; a CSV row
        # is one enormous "word", so a whole spreadsheet became a single
        # chunk - which then overflowed every context budget downstream and
        # produced "I don't have that in my provided sources" for a document
        # the system was holding (observed live). 1500 chars ~ the embedding
        # window; split oversized chunks on line boundaries where possible.
        MAXC = 1500
        out = []
        for c in chunks:
            while len(c) > MAXC:
                cut = c.rfind('\n', MAXC // 2, MAXC)
                if cut == -1:
                    cut = c.rfind(' ', MAXC // 2, MAXC)
                if cut == -1:
                    cut = MAXC
                out.append(c[:cut].strip())
                c = c[cut:].strip()
            if c:
                out.append(c)
        return out if out else chunks


_rag_manager = None


def get_rag_manager() -> SemanticRAGManager:
    global _rag_manager
    if _rag_manager is None:
        _rag_manager = SemanticRAGManager()
    return _rag_manager
