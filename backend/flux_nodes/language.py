#!/usr/bin/env python3
# Copyright (c) 2025 SNF-AI
# SPDX-License-Identifier: MIT

"""Language Node - OpenHermes-2.5-Mistral-7B."""

import logging
import os
from pathlib import Path
from typing import Optional

from .base import FluxNode

logger = logging.getLogger(__name__)


class LanguageNode(FluxNode):
    """Language expert node using Mistral-7B (shared instance)."""

    def __init__(self, model_path: Optional[str] = None, node_id: str = "language-mistral-7b",
                 name: str = "Language (OpenHermes-Mistral-7B)",
                 description: str = "Language understanding and generation using Mistral-7B"):
        super().__init__(node_id, name, description)
        if model_path is None:
            from . import MODELS_DIR
            self.model_path = MODELS_DIR / "mistral-7b-instruct-q4.gguf"
        else:
            self.model_path = model_path

        if not os.path.exists(self.model_path):
            logger.error(f"Model file not found: {self.model_path}")
            self.is_available = False
            return

        self.keywords = {
            "text", "language", "chat", "conversation", "question", "answer", "explain",
            "describe", "tell", "what", "how", "why", "when", "where", "who", "write",
            "generate", "create", "help", "assist", "translate", "summarize", "essay",
            "story", "letter", "email", "report", "article", "paragraph", "sentence"
        }
        logger.info("LanguageNode ready (model loads on first query)")

    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        super().generate(prompt, **kwargs)
        conversation_history = kwargs.get('conversation_history', [])
        logger.info(f"LanguageNode generate called with prompt: {prompt[:100]}...")
        try:
            # Fetch at call time (do not cache): the shared cache keeps ONE
            # resident model and may have evicted ours for another node.
            from .shared_model import get_shared_model
            model = get_shared_model(self.model_path)

            formatted_prompt = self._format_prompt(prompt, conversation_history)
            response = model(
                formatted_prompt,
                # 320-token default cap: on CPU-only hosts generation runs
                # ~1 tok/s under load, so 512 tokens meant multi-minute worst
                # cases. Callers can tighten further (grounded answers pass
                # 220) but never exceed the cap.
                max_tokens=min(int(kwargs.get('max_tokens', 320)), 320),
                temperature=0.5, top_p=0.8, top_k=20,
                # Stop sequences: the grounded prompt ends "Question: X / Answer:",
                # and without these the model continues inventing extra Q/A
                # pairs - spilling unrelated (even confidential) retrieved
                # content into the answer and wasting minutes of generation.
                repeat_penalty=1.0,
                stop=["</s>", "\nQuestion:", "\n[Question", "\nQ:"], echo=False,
            )
            return response['choices'][0]['text'].strip()
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Error: {str(e)}"

    def _format_prompt(self, query_text: str, conversation_history: list = None) -> str:
        if not conversation_history:
            return f"[INST] {query_text} [/INST]"
        context_parts = []
        recent = conversation_history[-2:] if len(conversation_history) > 2 else conversation_history
        for msg in recent:
            if msg.get('role') == 'user':
                context_parts.append(f"Human: {msg.get('content', '')}")
            elif msg.get('role') == 'assistant':
                context_parts.append(f"Assistant: {msg.get('content', '')}")
        if context_parts:
            context = "\n".join(context_parts)
            # The reference-only framing matters: without it a 7B model
            # re-answers or riffs on earlier turns instead of the actual
            # question (seen in live testing).
            return (f"[INST] Previous conversation (for reference only):\n{context}\n\n"
                    f"Answer ONLY the following current question. Do not revisit or "
                    f"re-answer earlier questions unless the current question "
                    f"explicitly refers to them.\n\nCurrent question: {query_text} [/INST]")
        return f"[INST] {query_text} [/INST]"
