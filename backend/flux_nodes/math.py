#!/usr/bin/env python3

import logging
import operator
from pathlib import Path
from typing import Any, Optional

from .base import FluxNode
from . import MODELS_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama
except ImportError as e:
    logger.error(f"Error importing llama_cpp for MathNode: {e}")
    Llama = None


class MathNode(FluxNode):
    """Math node: fast deterministic path for simple arithmetic, Mistral LLM otherwise."""

    def __init__(self, model_path: Optional[Path] = None, node_id: str = "math-llm-eval",
                 name: str = "Math (LLM Eval)",
                 description: str = "Solves mathematical problems using a local LLM with a deterministic fallback.",
                 **kwargs: Any):
        super().__init__(node_id, name, description, **kwargs)
        self.keywords = {"math", "calculate", "compute", "solve", "equation", "sum", "product", "add", "subtract", "multiply", "divide"}
        if Llama is None:
            self.is_available = False
            return
        self.model_path = model_path or (MODELS_DIR / 'mistral-7b-instruct-q4.gguf')
        self.llm = None
        self.safe_ops = {'+': operator.add, '-': operator.sub, '*': operator.mul,
                         '/': operator.truediv, '^': operator.pow}
        # Available if the model file exists; the model itself loads lazily.
        self.is_available = Path(self.model_path).exists()

    def _ensure_model(self):
        if self.llm is None:
            from .shared_model import get_shared_model
            self.llm = get_shared_model(self.model_path)

    def safe_eval(self, query: str) -> Optional[str]:
        try:
            parts = query.split()
            if len(parts) == 3 and parts[1] in self.safe_ops:
                return str(self.safe_ops[parts[1]](float(parts[0]), float(parts[2])))
        except Exception as e:
            logger.warning(f"Safe eval failed for '{query}': {e}")
        return None

    def generate(self, query: str, **kwargs: Any) -> Optional[str]:
        if not self.is_available:
            return None
        safe_result = self.safe_eval(query)
        if safe_result is not None:
            return safe_result
        try:
            self._ensure_model()
            if self.llm is None:
                return "Math model unavailable."
            out = self.llm(f"Question: {query}\nAnswer:", max_tokens=1024,
                           stop=["</s>"], temperature=0.3, echo=False)
            return out['choices'][0]['text'].strip()
        except Exception as e:
            logger.error(f"Math LLM error: {e}")
            return f"Error: {e}"
