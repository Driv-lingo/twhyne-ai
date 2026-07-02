#!/usr/bin/env python3
"""RAG (Retrieval-Augmented Generation) Manager for Twhyne AI.

Stores documents, chunks them, and retrieves relevant passages by keyword
overlap. Filler/stop words are ignored when scoring so the meaningful terms in
a question drive retrieval (e.g. 'build', 'fence', 'giraffe' rather than
'how', 'can', 'i', 'a', 'for').
"""

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

_STOPWORDS = {
    "a", "an", "the", "is", "are", "am", "was", "were", "be", "been", "being",
    "i", "you", "he", "she", "it", "we", "they", "me", "my", "your", "our", "his",
    "her", "their", "this", "that", "these", "those", "to", "for", "of", "in", "on",
    "at", "by", "with", "from", "as", "and", "or", "but", "if", "so", "how", "what",
    "why", "when", "where", "who", "which", "can", "could", "do", "does", "did",
    "should", "would", "will", "shall", "may", "might", "please", "about", "into",
    "there", "here", "then", "than", "some", "any", "all",
}


def _content_words(text: str) -> set:
    return {w for w in text.lower().split() if w not in _STOPWORDS and len(w) > 1}


class SimpleRAGManager:
    """RAG manager using stopword-aware keyword matching (no heavy deps)."""

    def __init__(self, storage_dir: str = "rag_storage"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.datasets_file = self.storage_dir / "datasets.json"
        self.datasets = self._load_datasets()
        logger.info(f"RAG Manager initialized with storage at {self.storage_dir}")

    def _load_datasets(self) -> Dict[str, Any]:
        if self.datasets_file.exists():
            try:
                with open(self.datasets_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading datasets: {e}")
                return {}
        return {}

    def _save_datasets(self):
        try:
            with open(self.datasets_file, 'w') as f:
                json.dump(self.datasets, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving datasets: {e}")

    def get_status(self) -> Dict[str, Any]:
        return {"available": True, "backend": "keyword_matching",
                "datasets_count": len(self.datasets), "numpy_available": NUMPY_AVAILABLE}

    def list_datasets(self) -> List[Dict[str, Any]]:
        out = []
        for dataset_id, info in self.datasets.items():
            out.append({"id": dataset_id, "name": info.get("name", "Unnamed"),
                        "description": info.get("description", ""),
                        "document_count": len(info.get("documents", [])),
                        "is_available": True, "created_at": info.get("created_at", "")})
        return out

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
                for i, chunk in enumerate(self._chunk_text(content, chunk_size=500)):
                    documents.append({"id": f"{dataset_id}-doc-{len(documents)}",
                                      "source": filename, "content": chunk, "chunk_index": i})
                logger.info(f"Processed {filename}: chunks so far {len(documents)}")
            except Exception as e:
                logger.error(f"Error processing file {file_data.get('filename')}: {e}")
        self.datasets[dataset_id] = {"name": name, "description": description,
                                     "documents": documents, "created_at": str(uuid.uuid4())}
        self._save_datasets()
        logger.info(f"Created dataset '{name}' with {len(documents)} chunks")
        return {"id": dataset_id, "name": name, "description": description,
                "document_count": len(documents), "is_available": True}

    def delete_dataset(self, dataset_id: str) -> bool:
        if dataset_id in self.datasets:
            del self.datasets[dataset_id]
            self._save_datasets()
            return True
        return False

    def search_dataset(self, dataset_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if dataset_id not in self.datasets:
            logger.error(f"Dataset {dataset_id} not found")
            return []
        documents = self.datasets[dataset_id].get("documents", [])
        query_words = _content_words(query)
        if not query_words:
            return []
        query_lower = query.lower().strip()
        results = []
        for doc in documents:
            content_lower = doc["content"].lower()
            content_words = _content_words(content_lower)
            matching = query_words.intersection(content_words)
            if not matching:
                continue
            # Fraction of the question's meaningful words found in this chunk.
            score = len(matching) / max(len(query_words), 1)
            if query_lower in content_lower:
                score += 0.5
            results.append({"title": doc.get("source", "Unknown"), "content": doc["content"],
                            "score": round(score, 3), "source": doc.get("source", ""),
                            "chunk_index": doc.get("chunk_index", 0)})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        if not text:
            return []
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        return chunks if chunks else [text]

    def get_dataset_context(self, dataset_id: str, query: str, max_context_length: int = 2000) -> str:
        results = self.search_dataset(dataset_id, query, top_k=3)
        if not results:
            return ""
        parts, total = [], 0
        for r in results:
            content = r["content"]
            if total + len(content) > max_context_length:
                break
            parts.append(f"[Source: {r['source']}]\n{content}")
            total += len(content)
        return "\n\n".join(parts)


_rag_manager = None


def get_rag_manager() -> SimpleRAGManager:
    global _rag_manager
    if _rag_manager is None:
        _rag_manager = SimpleRAGManager()
    return _rag_manager
