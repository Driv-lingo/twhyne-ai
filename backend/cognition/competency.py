"""Competencies: bounded, executable, verified abstractions with a lifecycle.

A competency is NOT cached text or a previous answer. It is:
  parser    -> extracts typed parameters from a task (Tier 0/1 structural match)
  guards    -> two INDEPENDENT applicability checks that must both pass
               (formal/structural on the parameters; semantic on the task
               meaning). Disagreement => escalate to K.
  executor  -> a deterministic, registered Python callable
  verifier  -> post-conditions / invariants checked on the result
  evidence  -> successes, failures, counterexamples, FP/FN history
  economics -> measured latency, neural compute, verification cost, reuse
  lifecycle -> candidate -> R -> S, and back down on any bad signal

Levels
  K  knowledge-based: no competency applies -> full general reasoning
  R  rule-based: verified rule exists; explicit parameterisation + strong
     verification every time
  S  skill-based: repeatedly validated; cheap guards + light verification

Promotion is evidence- and economics-gated and always reversible. Nothing
is compiled after a single success. Rare long-tail work may stay K forever.

Storage: local JSON (rag_storage/competencies.json). No cloud, ever.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_LOCK = threading.RLock()

LEVELS = ('candidate', 'R', 'S')          # persisted competencies; K = "none applies"


def _storage_dir() -> Path:
    p = os.environ.get('TWHYNE_STATE_DIR')
    if p:
        return Path(p)
    base = os.environ.get('TWHYNE_AUDIT_LOG')
    if base:
        return Path(base).parent
    return Path(__file__).resolve().parent.parent / 'rag_storage'


# ---------------------------------------------------------------- registries
# Executors and parsers are CODE, referenced by name from persisted
# competencies, so a competency file can never smuggle in behaviour.
EXECUTORS: Dict[str, Callable[..., Any]] = {}
PARSERS: Dict[str, Callable[[str], Optional[Dict[str, Any]]]] = {}
SEMANTIC_GUARDS: Dict[str, Callable[[str, Dict[str, Any]], Tuple[bool, str]]] = {}
VERIFIERS: Dict[str, Callable[[Dict[str, Any], Any], Tuple[bool, str]]] = {}


def register_executor(name):
    def deco(fn):
        EXECUTORS[name] = fn; return fn
    return deco


def register_parser(name):
    def deco(fn):
        PARSERS[name] = fn; return fn
    return deco


def register_semantic_guard(name):
    def deco(fn):
        SEMANTIC_GUARDS[name] = fn; return fn
    return deco


def register_verifier(name):
    def deco(fn):
        VERIFIERS[name] = fn; return fn
    return deco


# ----------------------------------------------------------------- schema
@dataclass
class Envelope:
    """Formal applicability envelope: deterministic bounds on parameters and
    on task features. Anything outside => not applicable (no execution)."""
    required_params: List[str] = field(default_factory=list)
    param_types: Dict[str, str] = field(default_factory=dict)      # name -> int|float|str
    param_ranges: Dict[str, List[Optional[float]]] = field(default_factory=dict)  # name -> [lo, hi]
    forbidden_features: List[str] = field(default_factory=list)   # e.g. 'unit_conversion', 'extra_step'
    required_features: List[str] = field(default_factory=list)
    max_prompt_chars: int = 400


@dataclass
class Competency:
    id: str
    name: str
    type: str                                   # e.g. 'operator', 'composite'
    domain_path: List[str]                      # WDA decomposition location
    task_signature: str                         # e.g. 'percent_of(p, v)'
    level: str = 'candidate'                    # candidate | R | S
    parser: str = ''                            # PARSERS key
    executor: str = ''                          # EXECUTORS key
    semantic_guard: str = ''                    # SEMANTIC_GUARDS key
    verifier: str = ''                          # VERIFIERS key
    envelope: Envelope = field(default_factory=Envelope)
    parameters: Dict[str, Any] = field(default_factory=dict)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    verification_policy: str = 'full'           # full (R) | light (S)
    # evidence
    provenance: List[Dict[str, Any]] = field(default_factory=list)
    successes: int = 0
    failures: int = 0
    counterexamples: List[Dict[str, Any]] = field(default_factory=list)
    false_positives: int = 0                    # fired when it should not have
    false_negatives: int = 0                    # declined when it could have
    # structure
    dependencies: Dict[str, Any] = field(default_factory=dict)   # e.g. {'wda_version': 3}
    components: List[str] = field(default_factory=list)          # composite: member ids
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    valid_until: Optional[float] = None
    stale: bool = False
    promotion_history: List[Dict[str, Any]] = field(default_factory=list)
    rollback_history: List[Dict[str, Any]] = field(default_factory=list)
    # economics (measured)
    latency_s: List[float] = field(default_factory=list)          # last N
    neural_calls_saved: float = 0.0                                # est. per use, from K baseline
    verification_s: List[float] = field(default_factory=list)
    reuse_count: int = 0
    last_used: Optional[float] = None
    k_baseline_cost_s: Optional[float] = None                      # measured cost of the K path it replaces

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        d['envelope'] = Envelope(**(d.get('envelope') or {}))
        return cls(**d)

    # ---- applicability: two INDEPENDENT guards ---------------------------
    def formal_guard(self, params: Optional[Dict[str, Any]], features: Dict[str, bool],
                     prompt_len: int, deps: Dict[str, Any]) -> Tuple[bool, str]:
        """Deterministic structural check on the extracted parameters, task
        features, prompt size and dependency versions."""
        if self.stale or (self.valid_until and self.valid_until < time.time()):
            return False, 'competency stale/expired'
        for k, v in self.dependencies.items():
            if deps.get(k) is not None and deps[k] != v:
                return False, f'dependency {k} changed ({v} -> {deps[k]})'
        if params is None:
            return False, 'parser produced no parameters'
        env = self.envelope
        if prompt_len > env.max_prompt_chars:
            return False, 'prompt exceeds envelope length'
        for p in env.required_params:
            if p not in params or params[p] is None:
                return False, f'missing parameter {p}'
        for p, typ in env.param_types.items():
            v = params.get(p)
            if v is None:
                continue
            ok = {'int': lambda x: isinstance(x, int) and not isinstance(x, bool),
                  'float': lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
                  'str': lambda x: isinstance(x, str)}.get(typ, lambda x: True)(v)
            if not ok:
                return False, f'parameter {p} has wrong type'
        for p, (lo, hi) in env.param_ranges.items():
            v = params.get(p)
            if v is None:
                continue
            if lo is not None and v < lo:
                return False, f'parameter {p}={v} below envelope {lo}'
            if hi is not None and v > hi:
                return False, f'parameter {p}={v} above envelope {hi}'
        for f in env.forbidden_features:
            if features.get(f):
                return False, f'forbidden feature present: {f}'
        for f in env.required_features:
            if not features.get(f):
                return False, f'required feature absent: {f}'
        return True, 'formal guard passed'

    def semantic_check(self, prompt: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        g = SEMANTIC_GUARDS.get(self.semantic_guard)
        if g is None:
            return False, 'no semantic guard registered'
        try:
            return g(prompt, params)
        except Exception as e:
            return False, f'semantic guard error: {e}'

    # ---- lifecycle -------------------------------------------------------
    def record(self, ok: bool, latency_s: float, verify_s: float = 0.0,
               counterexample: Optional[Dict[str, Any]] = None):
        self.reuse_count += 1
        self.last_used = time.time()
        self.latency_s = (self.latency_s + [round(latency_s, 5)])[-50:]
        self.verification_s = (self.verification_s + [round(verify_s, 5)])[-50:]
        if ok:
            self.successes += 1
        else:
            self.failures += 1
            if counterexample:
                self.counterexamples.append({**counterexample, 'ts': time.time()})
        self.updated_at = time.time()

    def mean_latency(self) -> Optional[float]:
        return (sum(self.latency_s) / len(self.latency_s)) if self.latency_s else None

    def mean_verify(self) -> Optional[float]:
        return (sum(self.verification_s) / len(self.verification_s)) if self.verification_s else None


# --------------------------------------------------------------- economics
@dataclass
class PromotionPolicy:
    """Configurable, evidence-based thresholds. Defaults are deliberately
    conservative; the benchmark is what should tune them."""
    min_successes_for_R: int = 3
    min_successes_for_S: int = 8
    max_failure_rate_for_S: float = 0.0
    min_expected_value_ratio: float = 1.2       # EV must exceed cost by 20%
    learning_cost_s: float = 2.0                # amortised induction+replay cost
    maintenance_cost_s: float = 0.5             # per promotion, revalidation etc.
    error_risk_weight: float = 20.0             # cost assigned to one wrong S answer
    demote_on_failures: int = 1                 # any failure at S demotes


def expected_value(c: Competency, policy: PromotionPolicy,
                   expected_reuse: Optional[float] = None) -> Dict[str, float]:
    """EV(c) = ExpectedReuse x ExpectedSavings  vs
       Learning + Verification + Maintenance + ExpectedErrorRisk."""
    reuse = expected_reuse if expected_reuse is not None else float(max(c.reuse_count, c.successes))
    k_cost = c.k_baseline_cost_s if c.k_baseline_cost_s is not None else 0.0
    own = (c.mean_latency() or 0.0) + (c.mean_verify() or 0.0)
    savings = max(0.0, k_cost - own)
    n = max(1, c.successes + c.failures)
    fail_rate = c.failures / n
    ev = reuse * savings
    cost = (policy.learning_cost_s + (c.mean_verify() or 0.0) * reuse
            + policy.maintenance_cost_s + policy.error_risk_weight * fail_rate * reuse)
    return {'expected_reuse': reuse, 'expected_savings_s': round(savings, 4),
            'expected_value': round(ev, 4), 'cost': round(cost, 4),
            'ratio': round(ev / cost, 4) if cost else float('inf'),
            'fail_rate': round(fail_rate, 4)}


# ----------------------------------------------------------------- library
class CompetencyLibrary:
    def __init__(self, path: Optional[Path] = None, policy: Optional[PromotionPolicy] = None):
        self.path = path or (_storage_dir() / 'competencies.json')
        self.policy = policy or PromotionPolicy()
        self.items: Dict[str, Competency] = {}
        self._load()

    def _load(self):
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text())
                for cid, d in (raw.get('competencies') or {}).items():
                    self.items[cid] = Competency.from_dict(d)
        except Exception:
            self.items = {}

    def save(self):
        with _LOCK:
            tmp = self.path.with_suffix('.tmp')
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps({'competencies': {k: v.to_dict() for k, v in self.items.items()}},
                                      indent=1, sort_keys=True))
            tmp.replace(self.path)

    def add(self, c: Competency) -> Competency:
        with _LOCK:
            self.items[c.id] = c
            self.save()
        return c

    def get(self, cid: str) -> Optional[Competency]:
        return self.items.get(cid)

    def usable(self) -> List[Competency]:
        """R/S only. Candidates never execute for a user."""
        return [c for c in self.items.values() if c.level in ('R', 'S') and not c.stale]

    def by_signature(self, sig: str) -> List[Competency]:
        return [c for c in self.items.values() if c.task_signature == sig]

    # ---- lifecycle transitions (always reversible) ----------------------
    def consider_promotion(self, c: Competency, expected_reuse: Optional[float] = None) -> Dict[str, Any]:
        p = self.policy
        econ = expected_value(c, p, expected_reuse)
        n = c.successes + c.failures
        fail_rate = c.failures / n if n else 0.0
        before = c.level
        reason = 'insufficient evidence'
        if c.level == 'candidate' and c.successes >= p.min_successes_for_R and not c.counterexamples:
            if econ['ratio'] >= p.min_expected_value_ratio:
                c.level, reason = 'R', 'evidence + economics justify rule-level use'
            else:
                reason = 'economics do not justify compiling (rare/low-savings work stays K)'
        elif c.level == 'R' and c.successes >= p.min_successes_for_S and fail_rate <= p.max_failure_rate_for_S:
            if econ['ratio'] >= p.min_expected_value_ratio:
                c.level, c.verification_policy, reason = 'S', 'light', 'repeated validation; cheap guards suffice'
            else:
                reason = 'economics do not justify skill-level use'
        if c.level != before:
            c.promotion_history.append({'from': before, 'to': c.level, 'ts': time.time(),
                                        'successes': c.successes, 'econ': econ, 'reason': reason})
            c.version += 1
            self.save()
        return {'from': before, 'to': c.level, 'reason': reason, 'econ': econ}

    def demote(self, c: Competency, reason: str, to: Optional[str] = None) -> str:
        """S -> R -> candidate (invalidated = stale). Any bad signal moves DOWN."""
        before = c.level
        if to is None:
            to = {'S': 'R', 'R': 'candidate', 'candidate': 'candidate'}[c.level]
        c.level = to
        if to == 'candidate':
            c.stale = True                     # invalidated until re-inducted with new evidence
        c.verification_policy = 'full'
        c.rollback_history.append({'from': before, 'to': to, 'ts': time.time(), 'reason': reason})
        c.version += 1
        self.save()
        return to

    def refine_with_counterexample(self, c: Competency, prompt: str, params: Dict[str, Any],
                                   feature: Optional[str] = None) -> None:
        """Competency + counterexample -> refine envelope (forbid the feature
        that broke it) and demote one level. If no feature explains it, the
        rule itself is suspect -> invalidate."""
        c.counterexamples.append({'prompt': prompt[:200], 'params': params, 'feature': feature,
                                  'ts': time.time()})
        if feature:
            if feature not in c.envelope.forbidden_features:
                c.envelope.forbidden_features.append(feature)
            self.demote(c, f'counterexample: forbid feature {feature}')
        else:
            self.demote(c, 'counterexample without an explaining feature', to='candidate')

    def invalidate_stale(self, deps: Dict[str, Any]) -> List[str]:
        """Dependency versions moved (e.g. WDA changed): mark affected
        competencies stale so they require revalidation before use."""
        out = []
        for c in self.items.values():
            for k, v in c.dependencies.items():
                if deps.get(k) is not None and deps[k] != v and not c.stale:
                    c.stale = True
                    c.rollback_history.append({'from': c.level, 'to': c.level, 'ts': time.time(),
                                               'reason': f'stale: dependency {k} {v} -> {deps[k]}'})
                    out.append(c.id)
        if out:
            self.save()
        return out

    def conflicts(self, sig: str) -> List[Tuple[Competency, Competency]]:
        """Two usable competencies with the same signature whose envelopes
        overlap are a conflict; unless specificity resolves it, the caller
        must escalate to K rather than pick the cheaper one."""
        us = [c for c in self.usable() if c.task_signature == sig]
        out = []
        for i in range(len(us)):
            for j in range(i + 1, len(us)):
                out.append((us[i], us[j]))
        return out

    @staticmethod
    def more_specific(a: Competency, b: Competency) -> Optional[Competency]:
        """Deterministic precedence: the competency with strictly more
        required features / forbidden features / tighter ranges wins."""
        sa = (len(a.envelope.required_features) + len(a.envelope.forbidden_features)
              + len(a.envelope.param_ranges))
        sb = (len(b.envelope.required_features) + len(b.envelope.forbidden_features)
              + len(b.envelope.param_ranges))
        if sa == sb:
            return None
        return a if sa > sb else b


# ------------------------------------------------------- task features ---
_FEATURE_PATTERNS = {
    'unit_conversion': r'\b(in|into|to|expressed in)\s+(pounds|lbs?|kilograms?|kg|miles|km|kilomet|celsius|fahrenheit|kelvin|inches|cm|metres?|meters?)\b',
    'extra_step': r'\b(then|and then|after that|plus|added|added to|followed by|twice|again)\b',
    'tax': r'\btax\b',
    'negative_amount': r'-\$?\s?\d|\bnegative\b',
    'division_by_zero': r'\b(among|between|by|into)\s+(0|zero)\s+(people|persons|ways|parts|groups)\b',
    'question_of_possibility': r'\b(is (that|it) possible|can (they|we|each))\b',
}


def task_features(prompt: str) -> Dict[str, bool]:
    p = prompt.lower()
    return {name: bool(re.search(pat, p)) for name, pat in _FEATURE_PATTERNS.items()}
