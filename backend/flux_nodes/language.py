#!/usr/bin/env python3
# Copyright (c) 2025 SNF-AI
# SPDX-License-Identifier: MIT

"""
Language Node

This module implements the Language expert node using OpenHermes-2.5-Mistral-7B.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Import llama_cpp
from llama_cpp import Llama

from .base import FluxNode

logger = logging.getLogger(__name__)


class LanguageNode(FluxNode):
    """Language expert node using OpenHermes-2.5-Mistral-7B."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        node_id: str = "language-mistral-7b",
        name: str = "Language (OpenHermes-Mistral-7B)",
        description: str = "GPU-accelerated language understanding and generation using OpenHermes-2.5-Mistral-7B",
    ):
        """Initialize the language node."""
        logger.info(f"Starting LanguageNode initialization with node_id: {node_id}")
        super().__init__(node_id, name, description)
        logger.info("LanguageNode parent initialization complete")

        # Set model path
        logger.info("Setting model path...")
        if model_path is None:
            from . import MODELS_DIR
            self.model_path = MODELS_DIR / "mistral-7b-instruct-q4.gguf"
        else:
            self.model_path = model_path

        if not os.path.exists(self.model_path):
            logger.error(f"Model file not found: {self.model_path}")
            self.is_available = False
            return

        # Add keywords for language queries
        self.keywords = {
            "text", "language", "chat", "conversation", "question", "answer", "explain",
            "describe", "tell", "what", "how", "why", "when", "where", "who", "write",
            "generate", "create", "help", "assist", "translate", "summarize", "essay",
            "story", "letter", "email", "report", "article", "paragraph", "sentence"
        }

        # Model is loaded lazily on first query. This keeps startup fast and
        # keeps memory low on CPU-only machines (the model is ~4GB).
        self.model = None
        self.model_loaded = False
        logger.info("LanguageNode ready (model will load on first query)")

    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """Generate a response based on a prompt."""
        super().generate(prompt, **kwargs)  # Update last_used time
        conversation_history = kwargs.get('conversation_history', [])
        logger.info(f"LanguageNode generate called with prompt: {prompt[:100]}...")
        try:
            if not self.model_loaded or self.model is None:
                logger.info("Loading Mistral model on first use...")
                self._load_model()

            if not self.model_loaded or self.model is None:
                return "Sorry, the language model failed to load."

            formatted_prompt = self._format_prompt(prompt, conversation_history)

            response = self.model(
                formatted_prompt,
                max_tokens=512,
                temperature=0.5,
                top_p=0.8,
                top_k=20,
                repeat_penalty=1.0,
                stop=["</s>"],
                echo=False
            )

            result = response['choices'][0]['text'].strip()
            logger.info(f"Generated response: {result[:100]}...")
            return result

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Error: {str(e)}"

    def _load_model(self):
        """Load the language model (CPU).

        NOTE: use_mmap is intentionally False. On Docker Desktop (Windows/macOS)
        the model file is read through a slow shared-filesystem layer; memory
        mapping causes thousands of slow random reads. A single sequential read
        (use_mmap=False) loads the model far faster in that environment.
        """
        try:
            gpu_layers = 0
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_layers = 20
                    logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
            except Exception:
                pass

            logger.info(f"Loading Mistral-7B model from: {self.model_path} (mmap disabled)")

            self.model = Llama(
                model_path=str(self.model_path),
                n_ctx=2048,
                n_batch=512,
                use_mmap=False,      # sequential read - much faster over Docker file share
                use_mlock=False,
                n_threads=max(2, (os.cpu_count() or 4) - 1),
                n_gpu_layers=gpu_layers,
                verbose=False,
            )
            self.model_loaded = True
            logger.info("Mistral-7B model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.model = None
            self.model_loaded = False
            self.is_available = False

    def _format_prompt(self, query_text: str, conversation_history: list = None) -> str:
        """Format the prompt for the model with conversation history."""
        if not conversation_history:
            return f"[INST] {query_text} [/INST]"

        context_parts = []
        recent_history = conversation_history[-2:] if len(conversation_history) > 2 else conversation_history

        for msg in recent_history:
            if msg.get('role') == 'user':
                context_parts.append(f"Human: {msg.get('content', '')}")
            elif msg.get('role') == 'assistant':
                context_parts.append(f"Assistant: {msg.get('content', '')}")

        if context_parts:
            context = "\n".join(context_parts)
            return f"[INST] Previous conversation:\n{context}\n\nCurrent question: {query_text} [/INST]"
        else:
            return f"[INST] {query_text} [/INST]"
