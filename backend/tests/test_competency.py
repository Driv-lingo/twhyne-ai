"""Competency object, guards, lifecycle, economics - the negatives matter:
similarity is not applicability, one success never compiles a rule,
promotion is reversible, stale dependencies invalidate."""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["TWHYNE_STATE_DIR"] = tempfile.mkdtemp()

from cognition.competency import (  # noqa: E402
    Competency, CompetencyLibrary, PromotionPolicy, Envelope, task_features, expected_value,
)
from cognition import operators  # noqa: E402,F401  (registers templates)
from cognition.operators import TEMPLATES, fit_templates, extract_number, all_parses  # noqa: E402


def _lib():
    return CompetencyLibrary(Path(tempfile.mkdtemp()) / "c.json", PromotionPolicy())


def _pct():
    t = TEMPLATES['percent_of(p,v)']
    return Competency(id="pct@1", name=t['name'], type='operator', domain_path=t['domain_path'],
                      task_signature='percent_of(p,v)', parser=t['name'], executor=t['name'],
                      semantic_guard=t['name'], verifier=t['name'], envelope=t['envelope'])


def test_two_guards_are_independent_and_both_required():
    c = _pct()
    prompt = "What is 15% of 240?"
    params = {'p': 15.0, 'v': 240.0}
    f, _ = c.formal_guard(params, task_features(prompt), len(prompt), {})
    s, _ = c.semantic_check(prompt, params)
    assert f and s
    # near-match: same numbers, an extra step -> formal guard rejects (feature),
    # semantic guard also rejects; either alone would be enough to escalate.
    near = "What is 15% of 240, then add 10% tax?"
    f2, why = c.formal_guard(params, task_features(near), len(near), {})
    s2, _ = c.semantic_check(near, params)
    assert not f2 and 'extra_step' in why or 'tax' in why
    assert not s2
    # unit swap: the parser still extracts p,v (similar!) but meaning differs
    swap = "What is 20% of 500 kilograms, expressed in pounds?"
    f3, why3 = c.formal_guard(params, task_features(swap), len(swap), {})
    assert not f3 and 'unit_conversion' in why3


def test_stale_dependency_blocks_use():
    c = _pct(); c.dependencies = {'wda_version': 3}
    ok, why = c.formal_guard({'p': 1.0, 'v': 2.0}, {}, 10, {'wda_version': 4})
    assert not ok and 'dependency' in why
    lib = _lib(); c.level = 'S'; lib.add(c)
    assert lib.invalidate_stale({'wda_version': 4}) == ['pct@1'] and c.stale
    assert lib.usable() == []


def test_lifecycle_needs_evidence_and_is_reversible():
    lib = _lib(); c = _pct(); c.k_baseline_cost_s = 8.0; lib.add(c)
    # one success never compiles a rule
    c.record(True, 0.001, 0.001)
    assert lib.consider_promotion(c)['to'] == 'candidate'
    for _ in range(2):
        c.record(True, 0.001, 0.001)
    assert lib.consider_promotion(c)['to'] == 'R'
    for _ in range(5):
        c.record(True, 0.001, 0.001)
    assert lib.consider_promotion(c)['to'] == 'S' and c.verification_policy == 'light'
    assert [h['to'] for h in c.promotion_history] == ['R', 'S']
    # any bad signal moves DOWN, and a counterexample refines the envelope
    lib.refine_with_counterexample(c, "15% of 240 in pounds", {'p': 15, 'v': 240}, feature='unit_conversion')
    assert c.level == 'R' and 'unit_conversion' in c.envelope.forbidden_features
    lib.demote(c, 'unexplained failure', to='candidate')
    assert c.level == 'candidate' and c.stale and len(c.rollback_history) == 2


def test_economics_gate_keeps_rare_low_savings_work_at_K():
    lib = _lib(); c = _pct(); lib.add(c)
    c.k_baseline_cost_s = 0.01              # the K path was already cheap: no savings
    for _ in range(5):
        c.record(True, 0.01, 0.01)
    r = lib.consider_promotion(c)
    assert r['to'] == 'candidate' and 'economics' in r['reason']
    assert expected_value(c, lib.policy)['expected_savings_s'] == 0.0


def test_conflict_precedence_by_specificity():
    lib = _lib()
    a = _pct(); a.id = 'a'; a.level = 'S'
    b = _pct(); b.id = 'b'; b.level = 'S'
    b.envelope = Envelope(**{**a.envelope.__dict__, 'required_features': ['tax']})
    lib.add(a); lib.add(b)
    assert lib.more_specific(a, b) is b
    assert len(lib.conflicts('percent_of(p,v)')) == 1


def test_templates_reproduce_only_the_right_answer():
    assert extract_number("15% of 240 is 36.") == 36.0
    assert extract_number("The sale price is $180.") == 180.0
    fits = fit_templates("What is 15% of 240?", 36.0)
    assert [f['signature'] for f in fits] == ['percent_of(p,v)']
    assert fit_templates("What is 15% of 240?", 37.0) == []           # wrong answer: nothing reproduces
    fits = fit_templates("A $240 item is 25% off. What is the sale price?", 180.0)
    assert [f['signature'] for f in fits] == ['discount(p,v)']
    fits = fit_templates("Convert 68°F to Celsius.", 20.0)
    assert [f['signature'] for f in fits] == ['f_to_c(f)']
    fits = fit_templates("Plan a work day: tasks run one after another starting at 9:00. "
                         "A takes 3 hours, B takes 2 hours. At what hour does the last task finish?", 14.0)
    assert [f['signature'] for f in fits] == ['sequential_schedule(start,durations)']


def test_persistence_roundtrip():
    lib = _lib(); c = _pct(); c.level = 'R'; c.record(True, 0.002, 0.001); lib.add(c)
    lib2 = CompetencyLibrary(lib.path)
    c2 = lib2.get('pct@1')
    assert c2.level == 'R' and c2.successes == 1 and c2.envelope.forbidden_features == c.envelope.forbidden_features
    assert lib2.usable()[0].id == 'pct@1'


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); passed += 1; print(f"PASS {fn.__name__}")
        except Exception:
            print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
