#!/usr/bin/env python3
"""Shared llama.cpp model cache (single resident model).

Multiple expert nodes (Language, Math, Planner) use the SAME Mistral model
file, so one loaded instance serves all of them. Additionally, only ONE model
is kept in memory at a time: two 7B models resident together (e.g. Mistral +
CodeLlama) exceed a 12GB Docker VM and swap-thrash until every request times
out. Requesting a different model evicts the current one first. Nodes must
call get_shared_model() at generate time rather than caching the returned
object, so eviction actually frees the memory.
"""

import gc
import os
import threading
import logging

from llama_cpp import Llama

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cache = {}


def get_shared_model(model_path, **overrides):
    """Return a shared Llama instance for *model_path*, loading it once.

    Any previously loaded different model is evicted and freed first.
    """
    key = str(model_path)
    with _lock:
        model = _cache.get(key)
        if model is not None:
            return model

        for old_key in list(_cache):
            logger.info(f"Evicting {old_key} to make room for {key}")
            old = _cache.pop(old_key)
            try:
                old.close()
            except Exception:
                pass
            del old
        gc.collect()

        params = dict(
            n_ctx=8192,       # room for retrieved context + question + answer
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
