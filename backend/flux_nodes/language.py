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

import re

# Phrases that signal the user WANTS the long form; only then do we lift the
# focused-answer token cap. Everything else defaults to a concise answer.
_DETAIL_RE = re.compile(
    r'\b(in\s+detail|in\s+depth|in-depth|elaborate|comprehensive|'
    r'thorough(?:ly)?|detailed|deep\s+dive|step[-\s]by[-\s]step|'
    r'full\s+(?:explanation|breakdown)|explain\s+fully|expand\b|'
    r'long\s+version|everything\s+about|as\s+much\s+detail|essay|'
    r'write\s+(?:a|an)\s+(?:essay|article|report|letter|story))\b',
    re.IGNORECASE)


def _wants_detail(prompt: str) -> bool:
    return bool(_DETAIL_RE.search(prompt or ''))


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
            from .shared_model import get_shared_model, stopping_criteria_for
            model = get_shared_model(self.model_path)

            # Per-token cancellation: if the user cancels, this halts the
            # in-flight generation and frees INFER_LOCK for the next question.
            stop_crit = stopping_criteria_for(kwargs.get('client_request_id'))

            # RESPONSE DISCIPLINE (not a quality cut): on CPU every token costs
            # ~0.5s, so a 472-token answer to "explain a linked list" is ~4
            # minutes of waiting for detail nobody asked for. Default to a
            # FOCUSED answer and only generate the long form when the user
            # actually asks for depth. Same model, same reasoning - fewer
            # wasted tokens. The frontend can offer "Show more" to re-ask with
            # detail on demand.
            want_detail = _wants_detail(prompt)
            hard_ceiling = int(os.environ.get('TWHYNE_MAX_TOKENS', 900))
            focused_cap = int(os.environ.get('TWHYNE_FOCUSED_TOKENS', 320))
            ceiling = hard_ceiling if want_detail else min(focused_cap, hard_ceiling)
            eff_max = min(int(kwargs.get('max_tokens', ceiling)), ceiling)

            formatted_prompt = self._format_prompt(
                prompt, conversation_history, concise=not want_detail)
            import time as _t
            _t0 = _t.time()
            response = model(
                formatted_prompt,
                max_tokens=eff_max,
                temperature=0.5, top_p=0.8, top_k=20,
                # Stop sequences: the grounded prompt ends "Question: X / Answer:",
                # and without these the model continues inventing extra Q/A
                # pairs - spilling unrelated (even confidential) retrieved
                # content into the answer and wasting minutes of generation.
                repeat_penalty=1.0,
                stop=["</s>", "\nQuestion:", "\n[Question", "\nQ:"], echo=False,
                stopping_criteria=stop_crit,
            )
            # Perf transparency: log tokens/sec so slowness is diagnosable
            # from the launcher window (thread misconfig, paging, contention).
            try:
                dt = _t.time() - _t0
                toks = (response.get('usage') or {}).get('completion_tokens', 0)
                if dt > 0:
                    logger.info(f"Language generation: {toks} tokens in "
                                f"{dt:.0f}s ({toks/dt:.1f} tok/s)")
            except Exception:
                pass
            text = response['choices'][0]['text'].strip()
            # "Show more" affordance, text-side: only in focused mode, and only
            # when the model actually STOPPED (not truncated at the cap - a cut
            # answer should not also invite "more" as if it were complete).
            finish = (response.get('choices') or [{}])[0].get('finish_reason')
            if (not want_detail and finish != 'length'
                    and len(text) > 200):
                text += ("\n\n*Focused answer — ask “explain in detail” "
                         "for the long version.*")
            return text
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Error: {str(e)}"

    def _format_prompt(self, query_text: str, conversation_history: list = None,
                       concise: bool = False) -> str:
        directive = ("Answer in a focused way: a few clear sentences (or a "
                     "short list), no filler, no restating the question. "
                     if concise else "")
        if not conversation_history:
            return f"[INST] {directive}{query_text} [/INST]"
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
            return (f"[INST] {directive}Previous conversation (for reference only):\n{context}\n\n"
                    f"Answer ONLY the following current question. Do not revisit or "
                    f"re-answer earlier questions unless the current question "
                    f"explicitly refers to them.\n\nCurrent question: {query_text} [/INST]")
        return f"[INST] {directive}{query_text} [/INST]"
