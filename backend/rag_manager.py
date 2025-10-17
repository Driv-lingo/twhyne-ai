#!/usr/bin/env python3
"""
RAG (Retrieval-Augmented Generation) Manager for Twhyne AI
Handles document storage, embedding, and retrieval for custom knowledge bases.
"""

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("NumPy not available - using basic similarity")

class SimpleRAGManager:
    """Simple RAG manager using basic text matching (no external dependencies)."""
    
    def __init__(self, storage_dir: str = "rag_storage"):
        """Initialize the RAG manager."""
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.datasets_file = self.storage_dir / "datasets.json"
        self.datasets = self._load_datasets()
        logger.info(f"RAG Manager initialized with storage at {self.storage_dir}")
    
    def _load_datasets(self) -> Dict[str, Any]:
        """Load datasets from storage."""
        if self.datasets_file.exists():
            try:
                with open(self.datasets_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading datasets: {e}")
                return {}
        return {}
    
    def _save_datasets(self):
        """Save datasets to storage."""
        try:
            with open(self.datasets_file, 'w') as f:
                json.dump(self.datasets, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving datasets: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get RAG system status."""
        return {
            "available": True,
            "backend": "simple_text_matching",
            "datasets_count": len(self.datasets),
            "numpy_available": NUMPY_AVAILABLE
        }
    
    def list_datasets(self) -> List[Dict[str, Any]]:
        """List all available datasets."""
        datasets_list = []
        for dataset_id, dataset_info in self.datasets.items():
            datasets_list.append({
                "id": dataset_id,
                "name": dataset_info.get("name", "Unnamed"),
                "description": dataset_info.get("description", ""),
                "document_count": len(dataset_info.get("documents", [])),
                "is_available": True,
                "created_at": dataset_info.get("created_at", "")
            })
        return datasets_list
    
    def create_dataset(self, name: str, description: str, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a new RAG dataset from uploaded files."""
        dataset_id = f"rag-{uuid.uuid4().hex[:8]}"
        
        # Process documents
        documents = []
        for file_data in files:
            try:
                content = file_data.get("content", "")
                filename = file_data.get("filename", "unknown")
                
                # Decode base64 if needed
                if file_data.get("encoding") == "base64":
                    import base64
                    content = base64.b64decode(content).decode('utf-8', errors='ignore')
                
                # Split into chunks (simple approach)
                chunks = self._chunk_text(content, chunk_size=500)
                
                for i, chunk in enumerate(chunks):
                    documents.append({
                        "id": f"{dataset_id}-doc-{len(documents)}",
                        "source": filename,
                        "content": chunk,
                        "chunk_index": i
                    })
                
                logger.info(f"Processed {filename}: {len(chunks)} chunks")
            except Exception as e:
                logger.error(f"Error processing file {file_data.get('filename')}: {e}")
        
        # Store dataset
        dataset_info = {
            "name": name,
            "description": description,
            "documents": documents,
            "created_at": str(uuid.uuid4())
        }
        
        self.datasets[dataset_id] = dataset_info
        self._save_datasets()
        
        logger.info(f"Created dataset '{name}' with {len(documents)} document chunks")
        
        return {
            "id": dataset_id,
            "name": name,
            "description": description,
            "document_count": len(documents),
            "is_available": True
        }
    
    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset."""
        if dataset_id in self.datasets:
            del self.datasets[dataset_id]
            self._save_datasets()
            logger.info(f"Deleted dataset {dataset_id}")
            return True
        return False
    
    def search_dataset(self, dataset_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search a dataset for relevant documents."""
        if dataset_id not in self.datasets:
            logger.error(f"Dataset {dataset_id} not found")
            return []
        
        documents = self.datasets[dataset_id].get("documents", [])
        
        # Simple keyword-based search
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        results = []
        for doc in documents:
            content_lower = doc["content"].lower()
            
            # Calculate simple relevance score
            # Count matching words
            content_words = set(content_lower.split())
            matching_words = query_words.intersection(content_words)
            score = len(matching_words) / max(len(query_words), 1)
            
            # Boost score if query appears as substring
            if query_lower in content_lower:
                score += 0.5
            
            if score > 0:
                results.append({
                    "title": doc.get("source", "Unknown"),
                    "content": doc["content"],
                    "score": score,
                    "source": doc.get("source", ""),
                    "chunk_index": doc.get("chunk_index", 0)
                })
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks."""
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
        """Get relevant context from a dataset for a query."""
        results = self.search_dataset(dataset_id, query, top_k=3)
        
        if not results:
            return ""
        
        # Combine top results into context
        context_parts = []
        total_length = 0
        
        for result in results:
            content = result["content"]
            if total_length + len(content) > max_context_length:
                break
            context_parts.append(f"[Source: {result['source']}]\n{content}")
            total_length += len(content)
        
        return "\n\n".join(context_parts)

# Global RAG manager instance
_rag_manager = None

def get_rag_manager() -> SimpleRAGManager:
    """Get or create the global RAG manager instance."""
    global _rag_manager
    if _rag_manager is None:
        _rag_manager = SimpleRAGManager()
    return _rag_manager
