"""Condition D through the real Flask app, with no model present:
a matured competency answers /query at Tier 0; the same prompt in
'current' / 'structured' mode never executes a competency; the trace
records level, tier, guards and zero neural calls."""
import os
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_D = tempfile.mkdtemp()
os.environ["TWHYNE_STATE_DIR"] = _D
os.environ["TWHYNE_TRACE_LOG"] = os.path.join(_D, "t.jsonl")
os.environ.setdefault("TWHYNE_AUDIT_LOG", os.path.join(_D, "audit.jsonl"))
stub = types.ModuleType("llama_cpp"); stub.Llama = object
sys.modules.setdefault("llama_cpp", stub)

from cognition import runtime, trace  # noqa: E402


def _mature_percent_of():
    runtime.reset()
    ctl = runtime.get_controller()
    solves = [("What is 15% of 240?", "36"), ("Calculate 20 percent of 500.", "100"),
              ("10% of 80 equals what?", "8"), ("Find 25 per cent of 400.", "100"),
              ("If I take 5% of 1000, what do I get?", "50"), ("Compute 40% × 250.", "100"),
              ("What is 30% of 900?", "270"), ("Calculate 12 percent of 300.", "36"),
              ("What is 50% of 64?", "32"), ("Find 20 per cent of 45.", "9"), ("What is 10% of 1200?", "120")]
    for p, a in solves:
        trace.begin("seed", p, "full"); ctl.post_k(p, a, 6.0, "full"); trace.end()
    c = ctl.lib.by_signature("percent_of(p,v)")[0]
    assert c.level == "S"
    return ctl


def _app():
    import server
    return server.create_app().test_client()


def test_full_mode_tier0_answers_without_a_model():
    _mature_percent_of()
    c = _app()
    r = c.post("/query", json={"prompt": "Compute 35% × 200.", "mode": "full", "client_request_id": "d1"})
    d = r.get_json()
    assert r.status_code == 200, d
    assert d["response"].startswith("70")
    assert d["node_id"].startswith("competency:")
    assert d["competency"]["level"] == "S" and d["competency"]["tier"] == 0
    tr = d["trace"]
    assert tr["level"] == "S" and tr["tier"] == 0 and tr["neural_calls"] == 0
    assert tr["selected"] == d["competency"]["id"]
    assert all(g["formal"] and g["semantic"] for g in tr["guards"].values())
    assert d["verification"]["V_A"] == "both guards passed"


def test_ood_near_match_in_full_mode_escalates():
    _mature_percent_of()
    c = _app()
    r = c.post("/query", json={"prompt": "What is 35% of 200 kilograms, expressed in pounds?",
                               "mode": "full", "client_request_id": "d2"})
    d = r.get_json()
    tr = d.get("trace") or {}
    assert not str(d.get("node_id", "")).startswith("competency:")
    assert tr.get("level") != "S"
    assert tr.get("escalation") and "K" in tr["escalation"]


def test_structured_and_current_modes_never_execute_competencies():
    _mature_percent_of()
    c = _app()
    for mode in ("structured", "current"):
        r = c.post("/query", json={"prompt": "Compute 35% × 200.", "mode": mode, "client_request_id": f"m-{mode}"})
        d = r.get_json()
        assert not str(d.get("node_id", "")).startswith("competency:"), mode
        assert (d.get("trace") or {}).get("level") != "S", mode


def test_structured_mode_reports_verification_dimensions():
    # fresh, empty state directory: this test must not see competencies
    # seeded on disk by the condition-D tests above
    os.environ["TWHYNE_STATE_DIR"] = tempfile.mkdtemp()
    runtime.reset()
    assert runtime.get_library().items == {}
    c = _app()
    # deterministic SymPy answer, no model: post-K still labels the dimensions
    r = c.post("/query", json={"prompt": "What is 715 * 11?", "mode": "structured", "client_request_id": "s1"})
    d = r.get_json()
    v = d.get("verification") or {}
    assert v.get("V_U") == "answered" and "V_L" in v and "V_G" in v
    assert runtime.get_library().items == {}          # C never learns


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
