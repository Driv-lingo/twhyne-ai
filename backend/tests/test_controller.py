"""The whole loop, without a model: verified K solves -> candidate ->
evidence-gated promotion -> Tier-0 execution on NEW surface forms -> OOD
near-match escalates -> distribution shift -> return. Plus: structured mode
never learns, one success never compiles, conflicts go to K."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["TWHYNE_STATE_DIR"] = tempfile.mkdtemp()
os.environ["TWHYNE_TRACE_LOG"] = os.path.join(tempfile.mkdtemp(), "t.jsonl")

from cognition import trace  # noqa: E402
from cognition.competency import CompetencyLibrary, PromotionPolicy  # noqa: E402
from cognition.controller import Controller  # noqa: E402
from cognition.state import WorkDomainModel  # noqa: E402
from cognition import operators  # noqa: E402,F401

K_COST = 6.0   # a "measured" neural cost per K solve for these tests


def _ctl(policy=None):
    d = Path(tempfile.mkdtemp())
    lib = CompetencyLibrary(d / "c.json", policy or PromotionPolicy())
    return Controller(lib, WorkDomainModel(d / "w.json"))


def _k_solve(ctl, prompt, answer, mode="full"):
    """Simulate the K path: the model answered `answer`; run post-K checks."""
    trace.begin("t", prompt, mode)
    dims = ctl.post_k(prompt, answer, K_COST, mode)
    trace.end()
    return dims


PCT = [("What is 15% of 240?", "15% of 240 is 36."),
       ("Calculate 20 percent of 500.", "20 percent of 500 = 100"),
       ("10% of 80 equals what?", "It equals 8."),
       ("Find 25 per cent of 400.", "That is 100."),
       ("If I take 5% of 1000, what do I get?", "You get 50."),
       ("Compute 40% × 250.", "= 100"),
       ("What is 30% of 900?", "270"),
       ("Calculate 12 percent of 300.", "36"),
       ("What is 50% of 64?", "32"),
       ("Find 20 per cent of 45.", "9"),
       ("What is 10% of 1200?", "120")]


def test_structured_mode_verifies_but_never_learns():
    ctl = _ctl()
    for p, a in PCT[:6]:
        d = _k_solve(ctl, p, a, mode="structured")
        assert d["V_L"] == "reproduced" and "induction" not in d
    assert ctl.lib.items == {}
    assert ctl.select("What is 35% of 200?").level == "K"


def test_wrong_answer_is_not_reproduced_and_not_learned():
    ctl = _ctl()
    d = _k_solve(ctl, "What is 15% of 240?", "It is 38.")
    assert d["V_L"] == "unverified" and "induction" not in d
    assert ctl.lib.items == {}


def test_full_mode_matures_K_to_R_to_S_and_executes_new_surface_forms():
    ctl = _ctl()
    # 1 verified solve -> candidate only (never compiled from one example)
    d = _k_solve(ctl, *PCT[0])
    c = ctl.lib.get(d["induction"]["competency"])
    assert c.level == "candidate" and c.successes == 1
    assert ctl.select("What is 35% of 200?").level == "K"           # candidates never execute
    # more verified solves -> R (evidence + economics: K cost 6s vs ~0s)
    for p, a in PCT[1:3]:
        _k_solve(ctl, p, a)
    assert c.level == "R"
    assert all(cx["rejected"] for cx in d["induction"]["counterexamples"])
    # R executes with FULL verification on a brand-new surface form
    sel = ctl.select("Compute 35% × 200.")
    assert sel.level == "R" and sel.tier == 0 and sel.competency.id == c.id
    r = ctl.execute(sel, "Compute 35% × 200.")
    assert r["ok"] and r["result"] == 70.0
    # keep solving -> S with light verification
    for p, a in PCT[3:]:
        _k_solve(ctl, p, a)
    assert c.level == "S" and c.verification_policy == "light"
    sel = ctl.select("What is 8% of 50?")
    assert sel.level == "S"
    assert ctl.execute(sel, "What is 8% of 50?")["result"] == 4.0
    # measured economics recorded, not assumed
    assert c.k_baseline_cost_s == K_COST and c.mean_latency() is not None


def test_ood_near_match_escalates_to_K_not_S():
    ctl = _ctl()
    for p, a in PCT:
        _k_solve(ctl, p, a)
    assert ctl.lib.by_signature("percent_of(p,v)")[0].level == "S"
    for ood in ["What is 15% of 240 kilograms, expressed in pounds?",
                "What is 15% of 240, then add 10% tax?",
                "Split 240 dollars equally among 0 people. How much does each get?"]:
        sel = ctl.select(ood)
        assert sel.level == "K", ood
        assert sel.competency is None
    # the guard record explains WHY (a false-negative to K is the safe bias)
    sel = ctl.select("What is 15% of 240 kilograms, expressed in pounds?")
    g = next(iter(sel.guards.values()))
    assert g["formal"] is False and "unit_conversion" in g["formal_why"]


def test_distribution_shift_then_return():
    ctl = _ctl()
    for p, a in PCT:
        _k_solve(ctl, p, a)
    # shift: a NEW operator family -> K (no competency), learned in turn
    for p, a in [("Convert 68°F to Celsius.", "20"), ("What is 50 degrees Fahrenheit in Celsius?", "10"),
                 ("Turn 212 Fahrenheit into Celsius.", "100")]:
        assert ctl.select(p).level == "K"
        _k_solve(ctl, p, a)
    assert ctl.lib.by_signature("f_to_c(f)")[0].level == "R"
    # return: the original family is still S
    assert ctl.select("What is 9% of 300?").level == "S"


def test_world_change_invalidates_and_requires_reinduction():
    ctl = _ctl()
    for p, a in PCT:
        _k_solve(ctl, p, a)
    c = ctl.lib.by_signature("percent_of(p,v)")[0]
    assert c.level == "S"
    ctl.wda.update([{"id": "x", "kind": "constraint", "level": "value", "name": "rounding policy changed"}])
    assert ctl.lib.invalidate_stale(ctl.deps()) == [c.id]
    assert ctl.select("What is 9% of 300?").level == "K"          # efficiently-wrong is not allowed
    _k_solve(ctl, "What is 9% of 300?", "27")                      # re-induction starts evidence over
    assert c.stale is False and c.level == "candidate" and c.successes == 1


def test_bad_execution_demotes_and_escalates():
    ctl = _ctl()
    for p, a in PCT:
        _k_solve(ctl, p, a)
    c = ctl.lib.by_signature("percent_of(p,v)")[0]
    # A wrong S-level answer with NO explaining feature means the rule itself
    # is suspect: invalidate (candidate + stale) rather than step down one
    # level - the system must never stay efficiently wrong.
    ctl.report_outcome(c.id, correct=False, prompt="What is 5% of 20?", params={"p": 5, "v": 20}, feature=None)
    assert c.level == "candidate" and c.stale and c.false_positives == 1 and c.rollback_history
    assert ctl.select("What is 5% of 20?").level == "K"
    # ...whereas a wrong answer EXPLAINED by a feature refines the envelope and demotes one level
    ctl2 = _ctl()
    for p, a in PCT:
        _k_solve(ctl2, p, a)
    c2 = ctl2.lib.by_signature("percent_of(p,v)")[0]
    ctl2.report_outcome(c2.id, correct=False, prompt="15% of 240 in pounds", params={"p": 15, "v": 240},
                        feature="unit_conversion")
    assert c2.level == "R" and not c2.stale and "unit_conversion" in c2.envelope.forbidden_features


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
