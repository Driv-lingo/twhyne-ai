"""Per-task execution trace - the measurement substrate for the architecture.

Every /query produces exactly one TaskTrace: which processing level ran
(K/R/S), which tier of the router answered, every neural call with its
token counts and timing, how long routing / retrieval / generation /
verification / tools took, CPU and RAM deltas, and the final verdict. The
trace is (a) returned on the response as `trace` and (b) appended to a
local JSONL file so the benchmark harness and the K/R/S controller can read
history. It is instrumentation, not debug output: the A/B/C/D comparison
and the competency economics are computed from it.

Nothing here estimates. A quantity the platform cannot measure (TTFT on the
non-streaming path, energy inside a VM) is recorded as null, never guessed.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

_local = threading.local()
_WRITE_LOCK = threading.Lock()

# Stage names emitted by server._set_progress -> trace segment they close.
_STAGE_SEGMENT = {
    'routing': 'router_s',
    'retrieving documents': 'retrieval_s',
    'queued': 'queue_s',
    'generating': 'generation_s',
    'computing': 'tool_s',
    'indexing': 'tool_s',
    'verifying': 'verification_s',
    'idle': None,
}


def _trace_path() -> Path:
    p = os.environ.get('TWHYNE_TRACE_LOG')
    if p:
        return Path(p)
    base = os.environ.get('TWHYNE_AUDIT_LOG')
    if base:
        return Path(base).parent / 'task_traces.jsonl'
    return Path(__file__).resolve().parent.parent / 'rag_storage' / 'task_traces.jsonl'


def _rss_mb() -> Optional[float]:
    try:
        with open('/proc/self/status') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return round(int(line.split()[1]) / 1024, 1)
    except Exception:
        pass
    return None


def _cpu_s() -> Optional[float]:
    try:
        import resource
        r = resource.getrusage(resource.RUSAGE_SELF)
        return r.ru_utime + r.ru_stime
    except Exception:
        return None


@dataclass
class ModelCall:
    node: str
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    gen_s: float
    ttft_s: Optional[float] = None   # null until a streaming path measures it
    tok_s: Optional[float] = None


@dataclass
class TaskTrace:
    task_id: str
    started: float
    mode: str = 'current'                 # plain | current | structured | full
    prompt_sha: str = ''
    level: Optional[str] = None           # K | R | S  (None = legacy path)
    tier: Optional[int] = None            # router tier that answered (0-3)
    segments: Dict[str, float] = field(default_factory=dict)
    model_calls: List[ModelCall] = field(default_factory=list)
    candidates: List[str] = field(default_factory=list)
    selected: Optional[str] = None        # competency / mechanism id
    why: Optional[str] = None
    guards: Dict[str, Any] = field(default_factory=dict)
    escalation: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)   # promotion/rollback etc.
    cpu_start: Optional[float] = None
    rss_start: Optional[float] = None
    _stage: Optional[str] = None
    _stage_t: float = 0.0

    # ---- segments ---------------------------------------------------------
    def stage(self, state: str):
        """Close the current segment and open the next (called by _set_progress)."""
        now = time.time()
        if self._stage is not None:
            seg = _STAGE_SEGMENT.get(self._stage)
            if seg:
                self.segments[seg] = round(self.segments.get(seg, 0.0) + (now - self._stage_t), 4)
        self._stage = state if _STAGE_SEGMENT.get(state) else None
        self._stage_t = now

    def add(self, segment: str, seconds: float):
        self.segments[segment] = round(self.segments.get(segment, 0.0) + float(seconds), 4)

    # ---- neural calls -----------------------------------------------------
    def model_call(self, node: str, usage: Optional[dict], gen_s: float,
                   ttft_s: Optional[float] = None):
        usage = usage or {}
        ct = usage.get('completion_tokens')
        self.model_calls.append(ModelCall(
            node=node, prompt_tokens=usage.get('prompt_tokens'),
            completion_tokens=ct, gen_s=round(float(gen_s), 4), ttft_s=ttft_s,
            tok_s=(round(ct / gen_s, 2) if ct and gen_s > 0 else None)))

    # ---- finish -----------------------------------------------------------
    def finish(self, result: Optional[dict] = None) -> Dict[str, Any]:
        self.stage('idle')
        total = time.time() - self.started
        cpu_now, rss_now = _cpu_s(), _rss_mb()
        result = result or {}
        out = {
            'task_id': self.task_id,
            'mode': self.mode,
            'prompt_sha': self.prompt_sha,
            'level': self.level,
            'tier': self.tier,
            'selected': self.selected,
            'why': self.why,
            'candidates': self.candidates,
            'guards': self.guards,
            'escalation': self.escalation,
            'events': self.events,
            'segments': self.segments,
            'total_s': round(total, 4),
            'model_calls': [asdict(m) for m in self.model_calls],
            'neural_calls': len(self.model_calls),
            'tokens_in': sum((m.prompt_tokens or 0) for m in self.model_calls),
            'tokens_out': sum((m.completion_tokens or 0) for m in self.model_calls),
            'ttft_s': next((m.ttft_s for m in self.model_calls if m.ttft_s is not None), None),
            'cpu_s': (round(cpu_now - self.cpu_start, 4)
                      if cpu_now is not None and self.cpu_start is not None else None),
            'rss_mb': rss_now,
            'gpu': None,          # not measured on the CPU image
            'energy_j': None,     # not exposed inside the Docker VM
            'result': {
                'node_id': result.get('node_id'),
                'grounded': result.get('grounded'),
                'cached': result.get('cached'),
                'verdict': (result.get('gates') or {}).get('verdict') if isinstance(result.get('gates'), dict) else None,
                'withheld': bool(result.get('quantity_upper_bound_violation')),
                'refused': bool(result.get('node_denied')) or ((result.get('gates') or {}).get('verdict') == 'refused' if isinstance(result.get('gates'), dict) else False),
            },
            'ts': self.started,
        }
        _append(out)
        return out


# ---- module API (thread-local current trace) --------------------------------
def begin(task_id: str, prompt: str = '', mode: str = 'current') -> TaskTrace:
    t = TaskTrace(task_id=task_id, started=time.time(), mode=mode or 'current',
                  prompt_sha=hashlib.sha256((prompt or '').encode()).hexdigest()[:16],
                  cpu_start=_cpu_s(), rss_start=_rss_mb())
    _local.trace = t
    return t


def current() -> Optional[TaskTrace]:
    return getattr(_local, 'trace', None)


def end() -> None:
    _local.trace = None


def stage(state: str) -> None:
    t = current()
    if t:
        t.stage(state)


def model_call(node: str, usage: Optional[dict], gen_s: float,
               ttft_s: Optional[float] = None) -> None:
    t = current()
    if t:
        t.model_call(node, usage, gen_s, ttft_s)


def note(**fields) -> None:
    """Set level/tier/selected/why/escalation or record guards on the current trace."""
    t = current()
    if not t:
        return
    for k, v in fields.items():
        if k == 'guards' and isinstance(v, dict):
            t.guards.update(v)
        elif k == 'candidates' and isinstance(v, (list, tuple)):
            t.candidates.extend(v)
        elif k == 'event':
            t.events.append(v)
        elif hasattr(t, k):
            setattr(t, k, v)


def timed(segment: str):
    """Context manager: add elapsed time to a named segment."""
    class _T:
        def __enter__(self):
            self.t0 = time.time(); return self
        def __exit__(self, *a):
            t = current()
            if t:
                t.add(segment, time.time() - self.t0)
    return _T()


_MAX_BYTES = 50 * 1024 * 1024


def _append(rec: dict) -> None:
    try:
        p = _trace_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with _WRITE_LOCK:
            if p.exists() and p.stat().st_size > _MAX_BYTES:
                p.rename(p.with_suffix('.1.jsonl'))
            with open(p, 'a') as f:
                f.write(json.dumps(rec, separators=(',', ':')) + '\n')
    except Exception:
        pass  # instrumentation must never break a request


def read_recent(limit: int = 1000) -> List[dict]:
    p = _trace_path()
    if not p.exists():
        return []
    try:
        lines = p.read_text().splitlines()[-limit:]
        return [json.loads(l) for l in lines if l.strip()]
    except Exception:
        return []
