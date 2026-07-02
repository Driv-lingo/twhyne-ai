#!/usr/bin/env python3
# Copyright (c) 2025 SNF-AI
# SPDX-License-Identifier: MIT

"""
Code Node

This module implements the Code expert node using CodeLlama-7B.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

from .base import FluxNode

logger = logging.getLogger(__name__)


class CodeNode(FluxNode):
    """Code expert node using CodeLlama-7B."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        node_id: str = "code-codellama-7b",
        name: str = "Code (CodeLlama-7B)",
        description: str = "Code generation and understanding using CodeLlama-7B",
    ):
        """Initialize the code node."""
        logger.info(f"Starting CodeNode initialization with node_id: {node_id}")
        super().__init__(node_id, name, description)
        logger.info("CodeNode parent initialization complete")

        # Set model path
        logger.info("Setting model path...")
        if model_path is None:
            from . import MODELS_DIR
            self.model_path = MODELS_DIR / "codellama-7b.q4_K_M.gguf"
        else:
            self.model_path = Path(model_path)

        if not os.path.exists(self.model_path):
            from . import MODELS_DIR
            alt_path = MODELS_DIR / "codellama-7b-q4.gguf"
            if os.path.exists(alt_path):
                logger.info(f"Found alternative model: {alt_path}")
                self.model_path = alt_path
            else:
                logger.error(f"No suitable CodeLlama model found near {self.model_path}")
                self.is_available = False
                return

        logger.info("CodeNode initialization complete")

    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """Generate a response based on a prompt."""
        conversation_history = kwargs.get('conversation_history', [])
        logger.info(f"CodeNode generate called with prompt: {prompt[:100]}... and {len(conversation_history)} history items")
        try:
            # Fetch from the SHARED single-resident cache at call time. Loading
            # a private CodeLlama copy while Mistral was resident put two 7B
            # models in a 12GB VM and swap-thrashed until requests timed out;
            # the shared cache evicts the other model before loading this one.
            from .shared_model import get_shared_model
            model = get_shared_model(self.model_path, n_ctx=4096)

            formatted_prompt = self._format_prompt(prompt, conversation_history)

            # 512 tokens is ample for a function + explanation; 1024 at CPU
            # speed (~3-4 tok/s) pushed a single request past 10 minutes.
            response = model(
                formatted_prompt,
                max_tokens=512,
                temperature=0.4,
                top_p=0.9,
                top_k=40,
                repeat_penalty=1.1,
                stop=["</s>"],
                echo=False
            )

            result = response['choices'][0]['text'].strip()
            logger.info(f"Generated response: {result[:100]}...")
            return result

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Error: {str(e)}"

    def _format_prompt(self, query_text: str, conversation_history: list = None) -> str:
        """Format the prompt for the code model."""
        return f"""You are a helpful coding assistant. Generate clean, working Python code for the following request:

Request: {query_text}

Please provide:
1. A complete Python script
2. Include necessary imports
3. Add comments explaining the code
4. Make it ready to run

Code:"""
