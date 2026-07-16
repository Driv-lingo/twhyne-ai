#!/usr/bin/env python3
"""Shared llama.cpp model cache (single resident model, fast swaps).

Multiple expert nodes (Language, Math, Planner) use the SAME Mistral model
file, so one loaded instance serves all of them. Only ONE model is kept in
memory at a time: two 7B models resident together exceed a 12GB Docker VM
and swap-thrash until every request times out. Requesting a different model
evicts the current one first. Nodes must call get_shared_model() at generate
time rather than caching the returned object, so eviction actually frees the
memory.

FAST SWAP: the mounted models volume crosses the Docker/Windows file-share
bridge, so re-reading 4GB on every model switch costs ~60s. On first load a
model is copied once to container-local disk and mmap'd from there; the OS
page cache then makes later swaps back to a recently-used model near-instant.
Falls back to reading the volume directly when local disk is tight.
Opt out with TWHYNE_FAST_SWAP=0.
"""

import gc
import os
import shutil
import threading
import logging
from pathlib import Path

from llama_cpp import Llama

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cache = {}

# Global inference lock: llama.cpp is NOT thread-safe, so ALL LLM
# generation serializes through this. Lives here (not server.py) so nodes
# that only sometimes need the LLM - like the math node's word-problem
# fallback - can take it themselves, while their deterministic paths
# (SymPy) stay lock-free and never queue behind a long generation.
INFER_LOCK = threading.Lock()

_LOCAL_CACHE_DIR = Path('/app/model_cache')


def _fast_local_copy(path: str):
    """Copy the model to container-local disk once. Returns (path, is_local)."""
    if os.environ.get('TWHYNE_FAST_SWAP', '1') == '0':
        return path, False
    src = Path(path)
    try:
        _LOCAL_CACHE_DIR.mkdir(exist_ok=True)
        dest = _LOCAL_CACHE_DIR / src.name
        if dest.exists() and dest.stat().st_size == src.stat().st_size:
            return str(dest), True
        free = shutil.disk_usage(_LOCAL_CACHE_DIR).free
        if free < src.stat().st_size * 1.2:
            logger.info(f"Fast-swap cache skipped for {src.name} (insufficient local disk)")
            return str(src), False
        logger.info(f"Caching {src.name} to local disk for fast swaps (one-time copy)...")
        tmp = dest.with_suffix('.part')
        shutil.copyfile(src, tmp)
        tmp.rename(dest)
        return str(dest), True
    except Exception as e:
        logger.warning(f"Fast-swap cache failed for {src}: {e}")
        return str(path), False


def _usable_cores():
    """Cores actually available to this process (respects cgroup/affinity
    limits Docker applies). This is the right n_threads for a container."""
    try:
        if hasattr(os, 'sched_getaffinity'):
            return max(1, len(os.sched_getaffinity(0)))
    except Exception:
        pass
    return max(1, os.cpu_count() or 2)


def _physical_cores():
    """Physical core count for n_threads. Hyperthreads HURT memory-
    bandwidth-bound inference, so all-logical-cores oversubscribed - but
    /proc/cpuinfo inside a VM (Docker Desktop/WSL2) can report every CPU
    as the same core, which would pin generation to 1-2 threads and make
    it several times SLOWER. Trust the topology only when it is plausible;
    never go below half the logical cores.
    """
    logical = os.cpu_count() or 4
    floor = max(2, logical // 2)
    try:
        pairs = set()
        cur = {}
        with open('/proc/cpuinfo') as f:
            for line in f:
                if line.startswith('physical id'):
                    cur['p'] = line.split(':')[1].strip()
                elif line.startswith('core id'):
                    pairs.add((cur.get('p', '0'), line.split(':')[1].strip()))
                elif not line.strip():
                    cur = {}
        if pairs:
            return max(len(pairs), floor)
    except Exception:
        pass
    return floor


def get_shared_model(model_path, **overrides):
    """Return a shared Llama instance for *model_path*, loading it once.

    Any previously loaded different model is evicted and freed first.
    """
    key = str(model_path)
    with _lock:
        model = _cache.get(key)
        if model is not None:
            return model

        # Residency budget: 1 model by default (12GB container). With more
        # memory (TWHYNE_MEM=18g + TWHYNE_MAX_RESIDENT=2) both 7Bs stay
        # loaded and the 2-4 minute code<->chat swap disappears entirely -
        # the single biggest speed lever on a big-RAM machine.
        max_resident = max(1, int(os.environ.get('TWHYNE_MAX_RESIDENT', '1')
                                  or 1))
        while len(_cache) >= max_resident:
            old_key = next(iter(_cache))
            logger.info(f"Evicting {old_key} to make room for {key}")
            old = _cache.pop(old_key)
            try:
                old.close()
            except Exception:
                pass
            del old
        gc.collect()

        load_path, is_local = _fast_local_copy(key)
        params = dict(
            n_ctx=8192,       # room for retrieved context + question + answer
            n_batch=512,
            # mmap from local disk: the OS page cache keeps recently used
            # models hot, so swapping back to one is near-instant. Over the
            # slow Docker volume bridge, a sequential full read is faster.
            use_mmap=is_local,
            # mlock pins weights in RAM - but ON by default it caused
            # memory pressure inside the 12g container ("failed to munlock
            # buffer: Cannot allocate memory", 0.9 tok/s observed live).
            # Now OPT-IN via TWHYNE_MLOCK=1 for machines with headroom.
            use_mlock=os.environ.get('TWHYNE_MLOCK', '0') in ('1', 'true'),
            # THREADS: use all USABLE cores by default. Inside Docker
            # Desktop's VM the vCPUs are the whole resource - there is no
            # host-hyperthread distinction to avoid, so the bare-metal
            # "physical cores only" halving just wasted half (a likely cause
            # of 0.9 tok/s). Override with TWHYNE_THREADS.
            n_threads=int(os.environ.get('TWHYNE_THREADS', '0') or 0)
            or max(2, _usable_cores()),
            n_gpu_layers=int(os.environ.get('TWHYNE_GPU_LAYERS', '0')),
            verbose=False,
        )
        params.update(overrides)
        # PERF DIAGNOSTIC: the #1 cause of slow CPU generation on Docker
        # Desktop is too few CPUs allocated to the VM. Log what the container
        # actually sees vs. the threads we chose, so "0.9 tok/s" becomes
        # "container has 2 CPUs" - actionable (raise Docker Desktop CPUs).
        try:
            import os as _os
            aff = len(_os.sched_getaffinity(0)) if hasattr(_os, 'sched_getaffinity') else _os.cpu_count()
            logger.info(f"CPU: container sees {_os.cpu_count()} logical / "
                        f"{aff} usable cores; using n_threads={params.get('n_threads')}, "
                        f"mlock={params.get('use_mlock')}, mmap={params.get('use_mmap')}. "
                        f"If tok/s is low, raise Docker Desktop CPUs "
                        f"(Settings > Resources) to at least host physical cores.")
        except Exception:
            pass
        logger.info(f"Loading shared model into memory: {load_path}")
        model = Llama(model_path=load_path, **params)
        _cache[key] = model
        logger.info(f"Shared model loaded: {key}")
        return model
