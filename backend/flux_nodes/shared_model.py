#!/usr/bin/env python3
"""Shared llama.cpp model cache.

Multiple expert nodes (Language, Math, Planner) use the SAME Mistral model
file. Loading a separate 4GB copy per node would exhaust RAM on normal
laptops. This module keeps one loaded instance per unique model path and
hands the same object to every node that requests it, so three Mistral-backed
nodes cost the memory of one.
"""

import os
import threading
import logging

from llama_cpp import Llama

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cache = {}


def get_shared_model(model_path, **overrides):
    """Return a shared Llama instance for *model_path*, loading it once."""
    key = str(model_path)
    with _lock:
        model = _cache.get(key)
        if model is None:
            params = dict(
                n_ctx=4096,       # room for retrieved context + question + answer
                n_batch=512,
                use_mmap=False,   # sequential read is far faster over Docker file shares
                use_mlock=False,
                n_threads=max(2, (os.cpu_count() or 4) - 1),
                n_gpu_layers=0,
                verbose=False,
            )
            params.update(overrides)
            logger.info(f"Loading shared model into memory: {key}")
            model = Llama(model_path=key, **params)
            _cache[key] = model
            logger.info(f"Shared model loaded: {key}")
        return model
