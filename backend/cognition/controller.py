"""K/R/S controller: tiered routing, two-guard applicability, level-appropriate
execution and verification, post-K verification dimensions, competency
induction, promotion and demotion.

The allocation question is "what is the cheapest ADEQUATE mechanism for this
unit of work?" - never "how can the model do it?". Deterministic execution
is preferred only when a competency is applicable under BOTH guards; any
disagreement, conflict, staleness or envelope violation escalates to K.

Tiers (each timed into the trace):
  0  exact/structural competency match (parser + formal guard + semantic guard)
  1  symbolic/rule/state matching   (the existing SymPy / timer / self paths,
     which run in the server before this gate)
  2  cheap semantic routing         (keyword scores; candidates only)
  3  full neural reasoning          (the existing pipeline) + post-K checks

Bias: false-negative routing to K is preferred over false-positive
execution of an invalid competency whenever consequences are meaningful.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import trace as _trace
from .competency import (Competency, CompetencyLibrary, EXECUTORS, PARSERS, VERIFIERS,
                         task_features, PromotionPolicy)
from .operators import TEMPLATES, fit_templates, extract_number, all_parses


@dataclass
class Selection:
    competency: Optional[Competency]
    params: Optional[Dict[str, Any]]
    level: str                       # 'S' | 'R' | 'K'
    tier: int
    candidates: List[str] = field(default_factory=list)
    guards: Dict[str, Any] = field(default_factory=dict)
    escalation: Optional[str] = None
    router_s: float = 0.0


class Controller:
    def __init__(self, library: CompetencyLibrary, wda=None, policy: Optional[PromotionPolicy] = None):
        self.lib = library
        self.wda = wda
        if policy:
            self.lib.policy = policy
        self._k_costs: Dict[str, List[float]] = {}   # signature -> measured K costs

    # ---- dependencies ----------------------------------------------------
    def deps(self) -> Dict[str, Any]:
        return {'wda_version': getattr(self.wda, 'version', None)}

    # ---- Tier 0: structural competency match ------------------------------
    def select(self, prompt: str, consequence: str = 'low') -> Selection:
        t0 = time.time()
        deps = self.deps()
        features = task_features(prompt)
        candidates, guards, matches = [], {}, []
        for c in self.lib.usable():
            parser = PARSERS.get(c.parser)
            if not parser:
                continue
            try:
                params = parser(prompt)
            except Exception:
                params = None
            if params is None:
                continue                                   # no structural match
            candidates.append(c.id)
            f_ok, f_why = c.formal_guard(params, features, len(prompt), deps)
            s_ok, s_why = c.semantic_check(prompt, params)
            guards[c.id] = {'formal': f_ok, 'formal_why': f_why,
                            'semantic': s_ok, 'semantic_why': s_why}
            if f_ok and s_ok:
                matches.append((c, params))
            elif f_ok != s_ok:
                guards[c.id]['disagreement'] = True
        sel_router = time.time() - t0
        if not matches:
            why = None
            if any(g.get('disagreement') for g in guards.values()):
                why = 'guard disagreement -> K'
            elif candidates:
                why = 'candidates failed guards -> K'
            return Selection(None, None, 'K', 3, candidates, guards, why, sel_router)
        # conflict: >1 applicable with the same signature -> specificity or K
        by_sig: Dict[str, List[Tuple[Competency, Dict[str, Any]]]] = {}
        for c, p in matches:
            by_sig.setdefault(c.task_signature, []).append((c, p))
        chosen: List[Tuple[Competency, Dict[str, Any]]] = []
        for sig, group in by_sig.items():
            if len(group) == 1:
                chosen.append(group[0]); continue
            winner = group[0]
            for other in group[1:]:
                ms = self.lib.more_specific(winner[0], other[0])
                if ms is None:
                    return Selection(None, None, 'K', 3, candidates, guards,
                                     f'unresolvable conflict between {winner[0].id} and {other[0].id} -> K',
                                     time.time() - t0)
                winner = (ms, winner[1] if ms is winner[0] else other[1])
            chosen.append(winner)
        if len(chosen) > 1:
            # Two different operators both claim the task: the task is not
            # unambiguous enough for cheap execution.
            return Selection(None, None, 'K', 3, candidates, guards,
                             'multiple operators applicable -> K', time.time() - t0)
        c, params = chosen[0]
        if consequence == 'high' and c.level != 'S':
            # meaningful consequences + not-yet-skill-level: still allowed at R
            # (full verification), but S is required for 'light' verification.
            pass
        return Selection(c, params, c.level, 0, candidates, guards, None, time.time() - t0)

    # ---- execute at R/S ---------------------------------------------------
    def execute(self, sel: Selection, prompt: str) -> Dict[str, Any]:
        c, params = sel.competency, sel.params
        t0 = time.time()
        try:
            result = EXECUTORS[c.executor](**params)
        except Exception as e:
            self.lib.demote(c, f'executor error: {e}')
            return {'ok': False, 'why': f'executor error: {e}', 'escalate': True}
        exec_s = time.time() - t0
        v0 = time.time()
        if c.verification_policy == 'full' or c.level == 'R':
            # R: strong verification - post-conditions AND independent
            # re-derivation must agree.
            ok, why = VERIFIERS[c.verifier](params, result) if c.verifier in VERIFIERS else (True, 'no verifier')
            if ok:
                again = EXECUTORS[c.executor](**params)
                ok = (again == result) or (isinstance(result, float) and math.isclose(again, result))
                why = why if ok else 'non-deterministic re-execution'
        else:
            # S: light verification - type/finiteness + post-condition only.
            ok = isinstance(result, (int, float)) and math.isfinite(result)
            why = 'light check' if ok else 'non-finite result'
            if ok and c.verifier in VERIFIERS:
                ok, why = VERIFIERS[c.verifier](params, result)
        verify_s = time.time() - v0
        c.record(ok, exec_s, verify_s)
        if not ok:
            self.lib.refine_with_counterexample(c, prompt, params, feature=None)
            _trace.note(event={'type': 'demotion', 'competency': c.id, 'reason': why})
            return {'ok': False, 'why': why, 'escalate': True}
        self.lib.save()
        return {'ok': True, 'result': result, 'exec_s': exec_s, 'verify_s': verify_s,
                'competency': c.id, 'level': c.level, 'signature': c.task_signature}

    # ---- post-K: verification dimensions + induction ----------------------
    def post_k(self, prompt: str, answer_text: str, k_cost_s: float, mode: str,
               grounded: bool = False, refused: bool = False) -> Dict[str, Any]:
        """Runs after a K-level (neural) answer.
        V_L: does exactly one known formula reproduce the committed number?
        V_A: (n/a at K)   V_G: groundedness as reported by the pipeline
        V_U: did we produce a usable answer (not refused / withheld)?
        In 'full' mode a reproduced answer feeds competency induction."""
        number = extract_number(answer_text)
        fits = fit_templates(prompt, number)
        v_l = 'reproduced' if len(fits) == 1 else ('ambiguous' if len(fits) > 1 else
                                                   ('no-number' if number is None else 'unverified'))
        dims = {'V_G': 'grounded' if grounded else 'ungrounded',
                'V_L': v_l, 'V_A': 'n/a (K)', 'V_U': 'refused' if refused else ('answered' if number is not None or answer_text else 'empty'),
                'fits': [f['signature'] for f in fits], 'number': number}
        if mode == 'full' and v_l == 'reproduced':
            dims['induction'] = self.induce(fits[0], prompt, k_cost_s)
        return dims

    # ---- induction --------------------------------------------------------
    def induce(self, fit: Dict[str, Any], prompt: str, k_cost_s: float) -> Dict[str, Any]:
        sig, name, params = fit['signature'], fit['name'], fit['params']
        t = TEMPLATES[sig]
        self._k_costs.setdefault(sig, []).append(k_cost_s)
        existing = self.lib.by_signature(sig)
        if existing:
            c = existing[0]
            if c.stale:
                # re-inducting after invalidation: evidence starts over
                c.stale = False; c.successes = 0; c.failures = 0; c.level = 'candidate'
                c.counterexamples = []
        else:
            c = Competency(id=f"{name}@{int(time.time())}", name=name, type='operator',
                           domain_path=list(t['domain_path']), task_signature=sig,
                           parser=name, executor=name, semantic_guard=name, verifier=name,
                           envelope=t['envelope'], dependencies=self.deps(),
                           provenance=[{'source': 'induction', 'prompt_sha': _sha(prompt), 'ts': time.time()}])
            self.lib.add(c)
            _trace.note(event={'type': 'candidate_created', 'competency': c.id, 'signature': sig})
        # 1-4: structured trace -> parameterised operator (the template already
        # generalises the structure); store the example for replay.
        examples = c.parameters.setdefault('examples', [])
        examples.append({'prompt': prompt[:300], 'params': params, 'expected': fit['result']})
        del examples[:-20]
        c.k_baseline_cost_s = sum(self._k_costs[sig]) / len(self._k_costs[sig])
        c.provenance.append({'source': 'verified_k_solve', 'prompt_sha': _sha(prompt), 'ts': time.time()})
        # 5: replay against previous applicable examples
        replay_ok, replay_why = self._replay(c)
        # 6: near-match counterexamples the guards must REJECT
        cx_ok, cx_report = self._counterexamples(c, prompt, params)
        c.record(replay_ok and cx_ok, 0.0, 0.0,
                 counterexample=None if (replay_ok and cx_ok) else {'prompt': prompt[:200], 'why': replay_why if not replay_ok else 'guards accepted a counterexample'})
        # 7-9: preconditions/postconditions verified in replay; promote only on evidence + economics
        promo = self.lib.consider_promotion(c)
        if promo['from'] != promo['to']:
            _trace.note(event={'type': f"promotion:{promo['from']}->{promo['to']}", 'competency': c.id,
                               'econ': promo['econ']})
        self.lib.save()
        return {'competency': c.id, 'level': c.level, 'successes': c.successes, 'failures': c.failures,
                'replay': replay_why, 'counterexamples': cx_report, 'promotion': promo}

    def _replay(self, c: Competency) -> Tuple[bool, str]:
        ex = c.parameters.get('examples') or []
        for e in ex:
            try:
                val = EXECUTORS[c.executor](**e['params'])
            except Exception as err:
                return False, f'replay error: {err}'
            if not math.isclose(float(val), float(e['expected']), rel_tol=0.005, abs_tol=0.011):
                return False, f"replay mismatch on '{e['prompt'][:40]}'"
            ok, why = VERIFIERS[c.verifier](e['params'], val)
            if not ok:
                return False, f'postcondition failed in replay: {why}'
        return True, f'replayed {len(ex)} example(s)'

    def _counterexamples(self, c: Competency, prompt: str, params: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
        """Perturb the prompt with the features this competency must not
        accept. If BOTH guards let one through, the competency is not safe
        to promote (a false positive waiting to happen)."""
        report, all_rejected = [], True
        t = TEMPLATES[c.task_signature]
        feats_deps = self.deps()
        for feature, suffix in t['perturbations']:
            cx = prompt.rstrip('.?') + suffix
            try:
                p2 = PARSERS[c.parser](cx)
            except Exception:
                p2 = None
            f_ok, f_why = c.formal_guard(p2, task_features(cx), len(cx), feats_deps) if p2 else (False, 'not parsed')
            s_ok, s_why = c.semantic_check(cx, p2 or {}) if p2 else (False, 'not parsed')
            rejected = not (f_ok and s_ok)
            all_rejected = all_rejected and rejected
            report.append({'feature': feature, 'rejected': rejected,
                           'formal': f_why, 'semantic': s_why})
            if not rejected:
                c.false_positives += 1
        return all_rejected, report

    # ---- runtime feedback -------------------------------------------------
    def report_outcome(self, competency_id: str, correct: bool, prompt: str = '', params=None, feature=None):
        """External judgement (benchmark / user) about an R/S answer."""
        c = self.lib.get(competency_id)
        if not c:
            return
        if correct:
            c.successes += 1
            self.lib.consider_promotion(c)
        else:
            c.false_positives += 1
            self.lib.refine_with_counterexample(c, prompt, params or {}, feature)
        self.lib.save()


def _sha(s: str) -> str:
    import hashlib
    return hashlib.sha256((s or '').encode()).hexdigest()[:16]
