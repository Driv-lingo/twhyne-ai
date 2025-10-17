#!/usr/bin/env python3

import logging
import math
import operator
from pathlib import Path
from typing import Any, Dict, Optional

from .base import FluxNode
from . import MODELS_DIR

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import dependencies and handle potential import errors
try:
    from llama_cpp import Llama
except ImportError as e:
    logger.error(f"Error importing dependencies for MathNode: {e}. Please install llama-cpp-python.")
    Llama = None

class MathNode(FluxNode):
    """A node for handling mathematical tasks using a local LLM with a safe fallback."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        node_id: str = "math-llm-eval",
        name: str = "Math (LLM Eval)",
        description: str = "Solves mathematical problems using a local LLM with a deterministic fallback.",
        **kwargs: Any,
    ):
        """Initialize the math node."""
        super().__init__(node_id, name, description, **kwargs)

        if Llama is None:
            self.is_available = False
            logger.error("MathNode is not available due to missing dependencies.")
            return

        # If no model path is provided, construct a default path
        if model_path is None:
            # Assume a 'models' directory at the project root
            project_root = Path(__file__).parent.parent.parent
            self.model_path = MODELS_DIR / 'mistral-7b-instruct-q4.gguf'
        else:
            self.model_path = model_path
        self.llm = None
        self.is_available = self._load_model()
        self.safe_ops = {
            '+': operator.add,
            '-': operator.sub,
            '*': operator.mul,
            '/': operator.truediv,
            '^': operator.pow,
        }

    def _load_model(self) -> bool:
        """Load the Llama.cpp model."""
        if self.model_path and self.model_path.exists():
            try:
                logger.info(f"Loading Llama.cpp model from {self.model_path}...")
                self.llm = Llama(model_path=str(self.model_path), n_ctx=4096, n_gpu_layers=-1)
                logger.info("Llama.cpp model loaded successfully.")
                return True
            except Exception as e:
                logger.error(f"Error loading Llama.cpp model: {e}", exc_info=True)
                return False
        else:
            logger.error(f"Model file not found at {self.model_path}")
            return False

    def safe_eval(self, query: str) -> Optional[str]:
        """A safe, deterministic evaluator for basic arithmetic."""
        try:
            # Very basic parsing for simple arithmetic
            parts = query.split()
            if len(parts) == 3 and parts[1] in self.safe_ops:
                op1, op, op2 = float(parts[0]), parts[1], float(parts[2])
                result = self.safe_ops[op](op1, op2)
                return str(result)
        except Exception as e:
            logger.warning(f"Safe eval failed for query '{query}': {e}")
        return None

    def generate(self, query: str, **kwargs: Any) -> Optional[str]:
        """Generate a response to a mathematical query."""
        if not self.is_available or self.llm is None:
            logger.warning("MathNode is not available or not properly initialized.")
            return None

        # First, try the safe, deterministic evaluator
        safe_result = self.safe_eval(query)
        if safe_result is not None:
            logger.info(f"Query '{query}' handled by safe evaluator.")
            return safe_result

        # If safe eval fails, use the LLM
        logger.info(f"Query '{query}' being handled by LLM.")
        prompt = f"Question: {query}\nAnswer:"
        try:
            output = self.llm(prompt, max_tokens=2048, stop=["\n", "</s>"], temperature=0.7, top_k=40, repeat_penalty=1.1, echo=False)
            response = output['choices'][0]['text'].strip()
            return response
        except Exception as e:
            logger.error(f"Error during LLM inference: {e}", exc_info=True)
            return None
