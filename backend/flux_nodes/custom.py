#!/usr/bin/env python3
"""Custom LLM node - loaded from the model registry (models/nodes.json).

Lets a user add ANY GGUF model (HuggingFace download or self-trained) as a
routed expert without touching code or rebuilding the image: drop the file
into the models folder and describe it in nodes.json. See
backend/nodes.example.json for the format.
"""

import logging
from pathlib import Path
from typing import Any, Optional

from .base import FluxNode

logger = logging.getLogger(__name__)


class CustomLLMNode(FluxNode):
    """A registry-defined expert backed by an arbitrary GGUF model."""

    def __init__(self, node_id: str, name: str, description: str,
                 model_path, keywords=None, prompt_template: Optional[str] = None,
                 n_ctx: int = 4096, max_tokens: int = 512, temperature: float = 0.5):
        super().__init__(node_id, name, description)
        self.model_path = Path(model_path)
        self.keywords = set(k.lower() for k in (keywords or []))
        self.prompt_template = prompt_template or "[INST] {prompt} [/INST]"
        self.n_ctx = n_ctx
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.metadata = {"source": "registry", "model_file": self.model_path.name}
        if not self.model_path.exists():
            logger.error(f"Custom node '{node_id}': model file missing: {self.model_path}")
            self.is_available = False

    def generate(self, prompt: str, **kwargs: Any) -> Optional[str]:
        try:
            # Shared single-resident cache: loading this model evicts the
            # previous one, so custom nodes obey the same memory budget.
            from .shared_model import get_shared_model
            model = get_shared_model(self.model_path, n_ctx=self.n_ctx)
            out = model(
                self.prompt_template.format(prompt=prompt),
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stop=["</s>"],
                echo=False,
            )
            return out['choices'][0]['text'].strip()
        except Exception as e:
            logger.error(f"Custom node '{self.node_id}' error: {e}")
            return f"Error: {e}"
