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
            logger.info(f"MODELS_DIR: {MODELS_DIR}")
            
            # Use the available Mistral model
            self.model_path = MODELS_DIR / "mistral-7b-instruct-q4.gguf"
            logger.info(f"Using Mistral-7B-Instruct model: {self.model_path}")
            logger.info(f"Checking if model file exists: {self.model_path}")
            
            # Verify model file exists
            if not os.path.exists(self.model_path):
                logger.error(f"Model file not found: {self.model_path}")
                # Try alternative name
                alt_path = MODELS_DIR / "mistral-7b-instruct-q4.gguf"
                if os.path.exists(alt_path):
                    logger.info(f"Found alternative model: {alt_path}")
                    self.model_path = alt_path
                else:
                    logger.error(f"No suitable Mistral model found in {MODELS_DIR}")
                    self.is_available = False
                    return
        else:
            self.model_path = model_path
        
        # Add keywords for language queries
        self.keywords = {
            "text", "language", "chat", "conversation", "question", "answer", "explain",
            "describe", "tell", "what", "how", "why", "when", "where", "who", "write",
            "generate", "create", "help", "assist", "translate", "summarize", "essay",
            "story", "letter", "email", "report", "article", "paragraph", "sentence"
        }
        
        # Initialize model
        self.model = None
        self.model_loaded = False
        
        # Pre-load model during initialization for faster inference
        logger.info("Pre-loading Mistral model for faster inference...")
        self._load_model()
        
        logger.info("LanguageNode initialization complete")

    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """Generate a response based on a prompt."""
        super().generate(prompt, **kwargs)  # Update last_used time
        conversation_history = kwargs.get('conversation_history', [])
        logger.info(f"LanguageNode generate called with prompt: {prompt[:100]}... and {len(conversation_history)} history items")
        try:
            # FORCE model to stay loaded - critical for sub-2s performance
            if not self.model_loaded or self.model is None:
                logger.error("CRITICAL: Model not pre-loaded! This should not happen.")
                return "Error: Model not ready. Please try again."
            
            if not self.model:
                logger.error("Failed to load model")
                return "Sorry, the language model is not available."
            
            # Format the prompt with conversation history
            formatted_prompt = self._format_prompt(prompt, conversation_history)
            
            # SPEED-OPTIMIZED generation for sub-2s latency
            response = self.model(
                formatted_prompt,
                max_tokens=1024,     # Reduced for CPU optimization
                temperature=0.5,     # Less creative for more accurate responses
                top_p=0.8,          # Adjusted for more natural output
                top_k=20,           # Fewer vocabulary options for faster responses
                repeat_penalty=1.0,  # No penalty to allow repetition
                stop=["</s>"],     # Only stop on end of sequence token
                echo=False
            )
            
            result = response['choices'][0]['text'].strip()
            logger.info(f"Generated response: {result[:100]}...")
            return result
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Error: {str(e)}"

    def _load_model(self):
        """Load the language model with GPU acceleration."""
        try:
            # Check GPU availability
            gpu_available = False
            gpu_layers = 0
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_available = True
                    gpu_layers = 16  # Use 16 GPU layers for balanced performance
                    gpu_name = torch.cuda.get_device_name(0)
                    gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
                    logger.info(f"GPU detected for LanguageNode: {gpu_name} ({gpu_memory:.1f} GB)")
                else:
                    logger.info("No GPU available for LanguageNode, using CPU only")
            except Exception as e:
                logger.warning(f"GPU detection failed for LanguageNode: {e}")
            
            device_info = "GPU-accelerated" if gpu_available else "CPU-only"
            logger.info(f"Loading Mistral-7B model from: {self.model_path} ({device_info})")
            logger.info(f"Using {gpu_layers} GPU layers for LanguageNode")
            
            self.model = Llama(
                model_path=str(self.model_path),
                n_ctx=4096,          # Increased context for better completion
                n_batch=16,          # Smaller batch for speed
                use_mmap=True,       # Memory mapping for faster loading
                use_mlock=False,     # Don't lock pages in RAM
                n_threads=8,         # Reduced threads for speed
                n_gpu_layers=gpu_layers,  # Dynamic GPU layers
                f16_kv=True,         # Half precision for speed
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
        
        # Build conversation context
        context_parts = []
        
        # Add recent conversation history (limit to last 2 messages for speed)
        recent_history = conversation_history[-2:] if len(conversation_history) > 2 else conversation_history
        
        for msg in recent_history:
            if msg.get('role') == 'user':
                context_parts.append(f"Human: {msg.get('content', '')}")
            elif msg.get('role') == 'assistant':
                context_parts.append(f"Assistant: {msg.get('content', '')}")
        
        # Combine context with current query
        if context_parts:
            context = "\n".join(context_parts)
            return f"[INST] Previous conversation:\n{context}\n\nCurrent question: {query_text} [/INST]"
        else:
            return f"[INST] {query_text} [/INST]"
