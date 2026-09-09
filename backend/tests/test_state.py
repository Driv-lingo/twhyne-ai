"""Phase 3 state schemas: persistent WDA, world/belief separation, task
state, decision relevance, hierarchical index. The negative cases are the
point: beliefs must not leak into W, ambiguity must not be collapsed, and
the whole model must never be what a prompt sees."""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["TWHYNE_STATE_DIR"] = tempfile.mkdtemp()

from cognition.state import (  # noqa: E402
    WorkDomainModel, BeliefStore, Alternative, TaskState, DomainIndex,
    decision_relevance, resolve_or_escalate,
)


def _wda():
    w = WorkDomainModel(Path(tempfile.mkdtemp()) / "wda.json")
    w.update([
        {"id": "snf", "kind": "purpose", "level": "purpose", "name": "Safe resident care"},
        {"id": "fall_safety", "kind": "value", "level": "value", "name": "Fall prevention", "parent": "snf"},
        {"id": "fall_assess", "kind": "function", "level": "function", "name": "Fall risk assessment", "parent": "fall_safety"},
        {"id": "morse", "kind": "process", "level": "process", "name": "Morse Fall Scale scoring",
         "parent": "fall_assess", "attrs": {"high_risk_threshold": 45}},
        {"id": "wristband", "kind": "resource", "level": "resource", "name": "Yellow wristband", "parent": "morse"},
        {"id": "bed_alarm", "kind": "resource", "level": "resource", "name": "Bed alarm", "parent": "morse"},
        {"id": "backup", "kind": "process", "level": "process", "name": "Nightly backup", "parent": "snf",
         "attrs": {"time": "02:00", "retention_days": 45}},
    ], source="snf_sample_policy")
    return w


def test_wda_is_persistent_and_incremental():
    w = _wda()
    v0 = w.version
    morse_v = w.nodes["morse"].version
    backup_v = w.nodes["backup"].version
    # incremental: only the touched node changes version/timestamp
    r = w.update([{"id": "backup", "kind": "process", "level": "process",
                   "attrs": {"retention_days": 60}}], source="policy_update_2026")
    assert r["changed"] == ["backup"] and w.version == v0 + 1
    assert w.nodes["backup"].version == backup_v + 1
    assert w.nodes["morse"].version == morse_v            # untouched
    assert w.nodes["backup"].provenance[-1]["source"] == "policy_update_2026"
    # no-op update changes nothing
    r2 = w.update([{"id": "backup", "kind": "process", "level": "process",
                    "attrs": {"retention_days": 60}}])
    assert r2["changed"] == [] and w.version == v0 + 1
    # persistence: a fresh instance reads the same state
    w2 = WorkDomainModel(w.path)
    assert w2.version == w.version and w2.nodes["backup"].attrs["retention_days"] == 60


def test_wda_rejects_observer_relative_facts():
    w = _wda()
    try:
        w.update([{"id": "mary", "kind": "entity", "level": "resource", "name": "Mary",
                   "attrs": {"location": "home", "believed_by": "john"}}])
        assert False, "beliefs must not enter W"
    except ValueError:
        pass


def test_decomposition_path_and_reduction():
    w = _wda()
    assert w.decomposition_path("wristband") == ["snf", "fall_safety", "fall_assess", "morse", "wristband"]
    star = w.reduce("morse fall scale high risk wristband", max_nodes=6)
    ids = [n["id"] for n in star["nodes"]]
    assert "morse" in ids and "wristband" in ids
    assert "backup" not in ids                     # irrelevant slice stays out
    assert len(star["nodes"]) <= 6                 # bounded: never the whole model
    assert "snf" in ids                            # ancestors come along for context


def test_world_vs_system_belief_vs_actor_belief():
    """World: Mary is home. Twhyne believes home (strong). John believes
    work. 'Where will John look for Mary?' must consult John's belief."""
    w = _wda()
    w.update([{"id": "mary", "kind": "entity", "level": "resource", "name": "Mary",
               "attrs": {"location": "home"}}], source="observation")
    b = BeliefStore(Path(tempfile.mkdtemp()) / "beliefs.json")
    b.believe("T", "mary.location", [Alternative("home", 0.9, [{"source": "observation"}]),
                                     Alternative("work", 0.1)], uncertainty="epistemic")
    b.believe("john", "mary.location", [Alternative("work", 1.0)], source="john_said")
    assert w.nodes["mary"].attrs["location"] == "home"
    assert b.best("T", "mary.location") == "home"
    assert b.best("john", "mary.location") == "work"     # queried from John's belief, not W
    d = b.disagreements("mary.location", world_value="home")
    assert d["conflict"] and d["observers"]["john"] == "work"
    # alternatives are kept, weights normalised - never collapsed to one symbol
    rec = b.query("T", "mary.location")
    assert len(rec["alternatives"]) == 2 and abs(sum(a["weight"] for a in rec["alternatives"]) - 1) < 1e-6


def test_decision_relevance_irrelevant_vs_relevant():
    exceeds = lambda lim: (lambda kg: "yes" if kg > lim else "no")
    # 10-12 kg vs a 5 kg limit: every alternative -> 'yes'  => irrelevant, act
    r = decision_relevance([{"value": 10, "weight": .5}, {"value": 12, "weight": .5}], exceeds(5))
    assert r["relevant"] is False and r["action"] == "yes"
    assert resolve_or_escalate(r, consequence="high") == "act"
    # 4-6 kg vs a 5 kg limit: alternatives -> 'no'/'yes'  => relevant
    r2 = decision_relevance([{"value": 4, "weight": .5}, {"value": 6, "weight": .5}], exceeds(5))
    assert r2["relevant"] is True and r2["expected_information_gain"] == 0.5
    assert resolve_or_escalate(r2, consequence="high") == "clarify"
    # low consequence with a strong majority may proceed with a caveat
    r3 = decision_relevance([{"value": 4, "weight": .05}, {"value": 6, "weight": .95}], exceeds(5))
    assert resolve_or_escalate(r3, consequence="low") == "act_with_caveat"


def test_task_state_is_compact_and_hierarchical():
    w = _wda()
    ts = TaskState(task_id="t1", goal={"classified": True},
                   domain_subset=w.reduce("morse score 47", max_nodes=5),
                   constraints=["use current policy"], consequence_of_error="high")
    ts.unresolved["score"] = [{"value": 47, "weight": 1.0}]
    ts.add_subgoal("classify risk", "threshold_compare", ["morse_threshold@1"])
    ts.add_subgoal("apply protocol", "lookup", ["wristband", "bed_alarm"])
    d = ts.to_dict()
    assert d["subgoals"][0]["operators"] == ["morse_threshold@1"]
    assert len(d["domain_subset"]["nodes"]) <= 5


def test_domain_index_is_structural_first():
    idx = DomainIndex()
    idx.register("pct@1", ["finance", "pricing", "percent", "percent_of"], "percent_of(p,v)", level="S")
    idx.register("disc@2", ["finance", "pricing", "percent", "discount"], "discount(p,v)", level="R")
    idx.register("f2c@1", ["units", "temperature", "convert", "f_to_c"], "f_to_c(f)", level="S")
    assert idx.by_signature("discount(p,v)") == ["disc@2"]
    assert set(idx.under(["finance", "pricing"])) == {"pct@1", "disc@2"}
    assert idx.exact(["units", "temperature", "convert", "f_to_c"]) == ["f2c@1"]
    idx.unregister("pct@1")
    assert idx.under(["finance"]) == ["disc@2"] and len(idx) == 2


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
