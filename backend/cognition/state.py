"""Core state schemas: work domain, beliefs, task state, decision relevance.

Four things that today's pipeline conflates or lacks entirely are kept
explicitly separate here:

  W_t      WorkDomainModel   actor-independent, persistent, incrementally
                             updated (W_{t+1} = Update(W_t, delta)); the
                             WDA abstraction hierarchy with decomposition,
                             provenance, versions, timestamps.
  B_T(W)   BeliefStore['T']  Twhyne's belief about the world - evidence,
                             alternatives, weights, sources, timestamps.
  B_i(W)   BeliefStore[i]    actor i's belief - may DISAGREE with W and B_T.
  G_t      TaskState         the compact, query-relevant task/control state
                             (CTA): goal, current, constraints, unresolved
                             variables, decisions, consequences, transitions.

Uncertainty is never collapsed to one asserted value: a proposition holds a
factorised set of alternatives with weights and an uncertainty class
(semantic / perceptual / epistemic / stochastic). Decision relevance is
computed, not assumed: an ambiguity that maps every alternative to the same
action is irrelevant and costs no further computation.

All storage is local JSON under rag_storage/. No embeddings, no cloud.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

_LOCK = threading.RLock()

# WDA abstraction levels (top -> bottom). Every node sits on exactly one.
LEVELS = ('purpose', 'value', 'function', 'process', 'resource')
KINDS = ('purpose', 'value', 'constraint', 'function', 'process', 'resource',
         'relationship', 'entity')
UNCERTAINTY = ('semantic', 'perceptual', 'epistemic', 'stochastic')


def _storage_dir() -> Path:
    p = os.environ.get('TWHYNE_STATE_DIR')
    if p:
        return Path(p)
    base = os.environ.get('TWHYNE_AUDIT_LOG')
    if base:
        return Path(base).parent
    return Path(__file__).resolve().parent.parent / 'rag_storage'


def _atomic_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True))
    tmp.replace(path)


def _tokens(text: str) -> set:
    return {t for t in re.findall(r'[a-z0-9_]+', (text or '').lower()) if len(t) > 2}


# =============================================================== W_t: WDA ==
@dataclass
class DomainNode:
    id: str
    kind: str                       # one of KINDS
    name: str
    level: str                      # one of LEVELS
    parent: Optional[str] = None    # decomposition (part-whole) parent
    attrs: Dict[str, Any] = field(default_factory=dict)
    relations: List[Dict[str, str]] = field(default_factory=list)  # {type, to}
    provenance: List[Dict[str, Any]] = field(default_factory=list)  # {source, ts, ref}
    version: int = 1
    updated_at: float = field(default_factory=time.time)
    valid_until: Optional[float] = None


class WorkDomainModel:
    """Persistent, actor-independent work-domain representation.

    Update is incremental: a delta touches only the nodes it names; every
    other node keeps its version and timestamp. Beliefs, intentions and
    partial observations are NOT accepted here (see BeliefStore) - a caller
    that tries to put an observer-qualified fact into W gets a ValueError.
    """

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (_storage_dir() / 'wda.json')
        self.nodes: Dict[str, DomainNode] = {}
        self.version = 0
        self.updated_at = 0.0
        self._load()

    # ---- persistence ------------------------------------------------------
    def _load(self):
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text())
                self.version = int(raw.get('version', 0))
                self.updated_at = float(raw.get('updated_at', 0.0))
                for nid, n in (raw.get('nodes') or {}).items():
                    self.nodes[nid] = DomainNode(**n)
        except Exception:
            self.nodes, self.version = {}, 0

    def save(self):
        with _LOCK:
            _atomic_write(self.path, {
                'version': self.version, 'updated_at': self.updated_at,
                'nodes': {k: asdict(v) for k, v in self.nodes.items()}})

    # ---- incremental update ----------------------------------------------
    def update(self, delta: Iterable[Dict[str, Any]], source: str = 'system') -> Dict[str, Any]:
        """Apply ops [{op: upsert|remove|relate, ...}]. Returns what changed."""
        changed, removed = [], []
        with _LOCK:
            now = time.time()
            for op in delta:
                kind_op = op.get('op', 'upsert')
                if kind_op == 'remove':
                    if op['id'] in self.nodes:
                        removed.append(op['id']); del self.nodes[op['id']]
                    continue
                if kind_op == 'relate':
                    n = self.nodes.get(op['id'])
                    if n is None:
                        raise KeyError(op['id'])
                    rel = {'type': op['type'], 'to': op['to']}
                    if rel not in n.relations:
                        n.relations.append(rel); n.version += 1; n.updated_at = now
                        changed.append(n.id)
                    continue
                # upsert
                for forbidden in ('believed_by', 'observer', 'belief', 'intends'):
                    if forbidden in op or forbidden in (op.get('attrs') or {}):
                        raise ValueError(
                            f"'{forbidden}' is observer-relative; put it in BeliefStore, not W")
                if op.get('kind') not in KINDS:
                    raise ValueError(f"unknown kind {op.get('kind')!r}")
                if op.get('level') not in LEVELS:
                    raise ValueError(f"unknown level {op.get('level')!r}")
                nid = op['id']
                prov = {'source': source, 'ts': now, 'ref': op.get('ref')}
                if nid in self.nodes:
                    n = self.nodes[nid]
                    before = (n.name, n.kind, n.level, n.parent, json.dumps(n.attrs, sort_keys=True))
                    n.name = op.get('name', n.name); n.kind = op['kind']; n.level = op['level']
                    n.parent = op.get('parent', n.parent)
                    n.attrs.update(op.get('attrs') or {})
                    n.valid_until = op.get('valid_until', n.valid_until)
                    after = (n.name, n.kind, n.level, n.parent, json.dumps(n.attrs, sort_keys=True))
                    if before != after:
                        n.version += 1; n.updated_at = now; n.provenance.append(prov)
                        changed.append(nid)
                else:
                    self.nodes[nid] = DomainNode(
                        id=nid, kind=op['kind'], name=op.get('name', nid), level=op['level'],
                        parent=op.get('parent'), attrs=dict(op.get('attrs') or {}),
                        provenance=[prov], valid_until=op.get('valid_until'))
                    changed.append(nid)
            if changed or removed:
                self.version += 1; self.updated_at = now
                self.save()
        return {'version': self.version, 'changed': changed, 'removed': removed}

    # ---- structure --------------------------------------------------------
    def children(self, nid: str) -> List[DomainNode]:
        return [n for n in self.nodes.values() if n.parent == nid]

    def ancestors(self, nid: str) -> List[str]:
        out, cur, guard = [], self.nodes.get(nid), 0
        while cur and cur.parent and guard < 50:
            out.append(cur.parent); cur = self.nodes.get(cur.parent); guard += 1
        return out

    def decomposition_path(self, nid: str) -> List[str]:
        """Decomposition path root -> nid (the hierarchical index key)."""
        return list(reversed(self.ancestors(nid))) + [nid]

    def stale(self, now: Optional[float] = None) -> List[str]:
        now = now or time.time()
        return [n.id for n in self.nodes.values() if n.valid_until and n.valid_until < now]

    # ---- query-relevant reduction  W_t -> W_t* ---------------------------
    def reduce(self, query: str, max_nodes: int = 24, seed_ids: Iterable[str] = ()) -> Dict[str, Any]:
        """Return only the slice of W a decision needs: nodes whose name/
        attrs match the query terms, their decomposition ancestors, and
        direct relations - bounded. This is what may enter a prompt; the
        whole model never does."""
        q = _tokens(query)
        scored: List[Tuple[int, str]] = []
        for n in self.nodes.values():
            hay = _tokens(n.name + ' ' + ' '.join(map(str, n.attrs.values())) + ' ' + ' '.join(n.attrs.keys()))
            s = len(q & hay)
            if s:
                scored.append((s, n.id))
        scored.sort(reverse=True)
        keep: List[str] = list(seed_ids)
        for _, nid in scored:
            if nid not in keep:
                keep.append(nid)
            if len(keep) >= max_nodes:
                break
        # ancestors + direct relations, still bounded
        extra: List[str] = []
        for nid in list(keep):
            for a in self.ancestors(nid):
                if a not in keep and a not in extra:
                    extra.append(a)
            for r in self.nodes.get(nid, DomainNode('', 'entity', '', 'resource')).relations:
                if r['to'] in self.nodes and r['to'] not in keep and r['to'] not in extra:
                    extra.append(r['to'])
        keep = (keep + extra)[:max_nodes]
        return {'version': self.version, 'query_terms': sorted(q),
                'nodes': [asdict(self.nodes[k]) for k in keep if k in self.nodes]}


# ============================================================= Beliefs ====
@dataclass
class Alternative:
    value: Any
    weight: float = 1.0
    evidence: List[Dict[str, Any]] = field(default_factory=list)  # {source, ts, ref}
    uncertainty: str = 'epistemic'
    depends_on: List[str] = field(default_factory=list)


class BeliefStore:
    """Factorised beliefs per observer.  key = 'entity.attribute'.

    'T' is Twhyne's own belief. Any other observer id is an actor. Values
    are alternatives with weights - never a single forced symbol. World
    state (W) lives in WorkDomainModel; a belief may agree with, disagree
    with, or be silent about W.
    """

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (_storage_dir() / 'beliefs.json')
        self.data: Dict[str, Dict[str, Dict[str, Any]]] = {}   # observer -> key -> record
        self._load()

    def _load(self):
        try:
            if self.path.exists():
                self.data = json.loads(self.path.read_text())
        except Exception:
            self.data = {}

    def save(self):
        with _LOCK:
            _atomic_write(self.path, self.data)

    def believe(self, observer: str, key: str, alternatives: List[Alternative] | List[Dict[str, Any]],
                source: str = 'system', uncertainty: Optional[str] = None,
                decision_relevant: Optional[bool] = None) -> Dict[str, Any]:
        alts = []
        for a in alternatives:
            if isinstance(a, Alternative):
                a = asdict(a)
            if uncertainty:
                a['uncertainty'] = uncertainty
            if a.get('uncertainty') not in UNCERTAINTY:
                a['uncertainty'] = 'epistemic'
            alts.append(a)
        total = sum(float(a.get('weight', 1.0)) for a in alts) or 1.0
        for a in alts:
            a['weight'] = round(float(a.get('weight', 1.0)) / total, 6)
        rec = {'alternatives': alts, 'source': source, 'observer': observer,
               'ts': time.time(), 'decision_relevant': decision_relevant}
        with _LOCK:
            self.data.setdefault(observer, {})[key] = rec
            self.save()
        return rec

    def query(self, observer: str, key: str) -> Optional[Dict[str, Any]]:
        return (self.data.get(observer) or {}).get(key)

    def best(self, observer: str, key: str) -> Optional[Any]:
        rec = self.query(observer, key)
        if not rec or not rec['alternatives']:
            return None
        return max(rec['alternatives'], key=lambda a: a['weight'])['value']

    def disagreements(self, key: str, world: Optional[WorkDomainModel] = None,
                      world_value: Any = None) -> Dict[str, Any]:
        """Who believes what about `key`, versus the world (if known)."""
        out = {'key': key, 'world': world_value, 'observers': {}}
        for obs, keys in self.data.items():
            if key in keys:
                out['observers'][obs] = self.best(obs, key)
        out['conflict'] = len({json.dumps(v, sort_keys=True) for v in out['observers'].values()}
                              | ({json.dumps(world_value, sort_keys=True)} if world_value is not None else set())) > 1
        return out


# ============================================================ Task state ==
@dataclass
class Transition:
    operator: str                # competency / mechanism id
    from_state: Dict[str, Any]
    to_state: Dict[str, Any]
    cost_estimate: Optional[float] = None
    verified: bool = False


@dataclass
class TaskState:
    """CTA-style compact control state for ONE task (G_t)."""
    task_id: str
    goal: Dict[str, Any]                                   # desired state
    current: Dict[str, Any] = field(default_factory=dict)  # relevant current state
    domain_subset: Dict[str, Any] = field(default_factory=dict)   # W*
    constraints: List[str] = field(default_factory=list)
    unresolved: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)  # var -> alternatives
    decisions: List[str] = field(default_factory=list)
    consequence_of_error: str = 'low'                       # low | medium | high
    transitions: List[Transition] = field(default_factory=list)
    subgoals: List[Dict[str, Any]] = field(default_factory=list)  # {goal, method, operators:[...]}

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    def add_subgoal(self, goal: str, method: str, operators: List[str]):
        self.subgoals.append({'goal': goal, 'method': method, 'operators': list(operators)})


# ===================================================== Decision relevance ==
def decision_relevance(alternatives: List[Dict[str, Any]],
                       action_for: Callable[[Any], Any]) -> Dict[str, Any]:
    """Is this ambiguity worth resolving?

    Maps every plausible alternative to the action it would imply. If all
    alternatives imply the SAME action the distinction is irrelevant: act.
    If they differ, the ambiguity is decision-relevant: escalate / gather
    information / ask. Also returns the weight of the majority action, an
    honest proxy for expected information gain (low weight on the minority
    action => resolving it changes little).
    """
    if not alternatives:
        return {'relevant': True, 'action': None, 'actions': {}, 'reason': 'no alternatives'}
    actions: Dict[str, float] = {}
    by_action: Dict[str, List[Any]] = {}
    for a in alternatives:
        act = action_for(a.get('value'))
        k = json.dumps(act, sort_keys=True, default=str)
        actions[k] = actions.get(k, 0.0) + float(a.get('weight', 1.0))
        by_action.setdefault(k, []).append(a.get('value'))
    total = sum(actions.values()) or 1.0
    if len(actions) == 1:
        k = next(iter(actions))
        return {'relevant': False, 'action': json.loads(k), 'actions': {k: 1.0},
                'reason': 'all alternatives imply the same action'}
    best_k = max(actions, key=actions.get)
    return {'relevant': True, 'action': None,
            'actions': {k: round(v / total, 4) for k, v in actions.items()},
            'majority_action': json.loads(best_k),
            'majority_weight': round(actions[best_k] / total, 4),
            'expected_information_gain': round(1.0 - actions[best_k] / total, 4),
            'reason': 'alternatives imply different actions'}


def resolve_or_escalate(rel: Dict[str, Any], consequence: str = 'low',
                        proceed_threshold: float = 0.9) -> str:
    """Policy: 'act' | 'act_with_caveat' | 'clarify'.
    Low-consequence + strong majority may act with a caveat; anything with
    meaningful consequences and real disagreement must clarify."""
    if not rel.get('relevant'):
        return 'act'
    if consequence == 'low' and rel.get('majority_weight', 0) >= proceed_threshold:
        return 'act_with_caveat'
    return 'clarify'


# ========================================================= Domain index ===
class DomainIndex:
    """Hierarchical competency/task index keyed by the WDA decomposition
    path: Domain -> Function -> Process -> TaskFamily -> Competency.

    Structural lookup comes FIRST; semantic similarity (if any) is only a
    secondary candidate source and never establishes applicability.
    """

    def __init__(self):
        self._by_path: Dict[Tuple[str, ...], List[str]] = {}
        self._by_signature: Dict[str, List[str]] = {}
        self._entries: Dict[str, Dict[str, Any]] = {}

    def register(self, entry_id: str, path: Iterable[str], signature: str, **meta):
        p = tuple(path)
        self._entries[entry_id] = {'path': p, 'signature': signature, **meta}
        self._by_path.setdefault(p, []).append(entry_id)
        for i in range(1, len(p) + 1):        # every prefix indexes it too
            self._by_path.setdefault(p[:i] + ('*',), []).append(entry_id)
        self._by_signature.setdefault(signature, []).append(entry_id)

    def unregister(self, entry_id: str):
        e = self._entries.pop(entry_id, None)
        if not e:
            return
        for k, v in list(self._by_path.items()):
            if entry_id in v:
                v.remove(entry_id)
        sig = self._by_signature.get(e['signature'])
        if sig and entry_id in sig:
            sig.remove(entry_id)

    def by_signature(self, signature: str) -> List[str]:
        return list(self._by_signature.get(signature, []))

    def under(self, path_prefix: Iterable[str]) -> List[str]:
        return list(self._by_path.get(tuple(path_prefix) + ('*',), []))

    def exact(self, path: Iterable[str]) -> List[str]:
        return list(self._by_path.get(tuple(path), []))

    def entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        return self._entries.get(entry_id)

    def __len__(self):
        return len(self._entries)
