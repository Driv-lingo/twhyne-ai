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
                # n_ctx=1024: document chunks are 350 WORDS (~500+ tokens),
                # which overflowed the previous 512-token window and made
                # embedding fail for large chunks - permanently, see
                # _ensure_embeddings.
                _embed_model = Llama(model_path=str(_EMBED_MODEL_FILE), embedding=True,
                                     n_ctx=1024, verbose=False)
                logger.info("Embedding model loaded (semantic retrieval enabled)")
    return _embed_model


def _embed(text: str) -> Optional[List[float]]:
    m = _get_embed_model()
    if m is None:
        return None
    try:
        out = m.create_embedding(text[:2000])
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


class SemanticRAGManager:
    """Embedding-based retrieval with a keyword fallback."""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or os.environ.get(
            'RAG_STORAGE', str(Path(__file__).resolve().parent / 'rag_storage')))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.datasets_file = self.storage_dir / "datasets.json"
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
            return int(self.datasets_file.stat().st_mtime)
        except Exception:
            return 0

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

    def create_dataset(self, name: str, description: str, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        dataset_id = f"rag-{uuid.uuid4().hex[:8]}"
        documents = []
        for file_data in files:
            try:
                content = file_data.get("content", "")
                filename = file_data.get("filename", "unknown")
                if file_data.get("encoding") == "base64":
                    import base64
                    content = base64.b64decode(content).decode('utf-8', errors='ignore')
                for i, chunk in enumerate(self._chunk_text(content, chunk_size=350)):
                    documents.append({"id": f"{dataset_id}-doc-{len(documents)}",
                                      "source": filename, "content": chunk,
                                      "chunk_index": i, "embedding": _embed(chunk)})
            except Exception as e:
                logger.error(f"Error processing file: {e}")
        self.datasets[dataset_id] = {"name": name, "description": description,
                                     "documents": documents, "created_at": str(uuid.uuid4())}
        self._matrix_cache.pop(dataset_id, None)
        self._save_datasets()
        logger.info(f"Created dataset '{name}' with {len(documents)} chunks")
        return {"id": dataset_id, "name": name, "description": description,
                "document_count": len(documents), "is_available": True}

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

    def search_dataset(self, dataset_id: str, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
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
                k = min(top_k, len(embdocs))
                idx = _np.argpartition(-sims, k - 1)[:k]
                idx = idx[_np.argsort(-sims[idx])]
                scored = [(float(sims[i]), embdocs[i]) for i in idx]
            else:
                scored = sorted(((_cosine(qv, d["embedding"]), d) for d in embdocs),
                                key=lambda x: x[0], reverse=True)[:top_k]
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
            matching = query_words.intersection(_content_words(doc["content"]))
            if matching:
                score = len(matching) / max(len(query_words), 1)
                results.append({"title": doc.get("source", ""), "content": doc["content"],
                                "score": round(score, 3), "source": doc.get("source", ""),
                                "chunk_index": doc.get("chunk_index", 0)})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _chunk_text(self, text: str, chunk_size: int = 350, overlap: int = 50) -> List[str]:
        if not text:
            return []
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        return chunks if chunks else [text]


_rag_manager = None


def get_rag_manager() -> SemanticRAGManager:
    global _rag_manager
    if _rag_manager is None:
        _rag_manager = SemanticRAGManager()
    return _rag_manager
