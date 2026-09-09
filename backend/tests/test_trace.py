"""Task-trace instrumentation: the measurement substrate must be exact,
must never estimate, and must never break a request."""
import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["TWHYNE_TRACE_LOG"] = os.path.join(tempfile.mkdtemp(), "traces.jsonl")

from cognition import trace  # noqa: E402


def test_segments_follow_progress_stages():
    t = trace.begin("t1", "what is 2+2", "current")
    trace.stage("routing"); time.sleep(0.01)
    trace.stage("generating"); time.sleep(0.01)
    out = t.finish({"node_id": "x"})
    trace.end()
    assert out["segments"]["router_s"] > 0
    assert out["segments"]["generation_s"] > 0
    assert out["total_s"] >= out["segments"]["router_s"]
    assert out["mode"] == "current" and out["task_id"] == "t1"


def test_model_calls_are_recorded_exactly_and_ttft_is_null_not_guessed():
    t = trace.begin("t2", "hi")
    trace.model_call("language-mistral-7b", {"prompt_tokens": 40, "completion_tokens": 20}, 10.0)
    trace.model_call("code-qwen-coder-7b", {"prompt_tokens": 10, "completion_tokens": 5}, 2.5)
    out = t.finish({})
    trace.end()
    assert out["neural_calls"] == 2
    assert out["tokens_in"] == 50 and out["tokens_out"] == 25
    assert out["model_calls"][0]["tok_s"] == 2.0
    assert out["ttft_s"] is None          # non-streaming path: unmeasured, not estimated
    assert out["energy_j"] is None and out["gpu"] is None


def test_note_and_events():
    t = trace.begin("t3", "x")
    trace.note(level="S", tier=0, selected="percent_of@3", why="formal+semantic guards passed",
               guards={"formal": True, "semantic": True}, candidates=["percent_of@3", "discount@1"])
    trace.note(event={"type": "promotion", "competency": "percent_of@3"})
    out = t.finish({"gates": {"verdict": "answered"}})
    trace.end()
    assert out["level"] == "S" and out["tier"] == 0
    assert out["guards"] == {"formal": True, "semantic": True}
    assert out["candidates"] == ["percent_of@3", "discount@1"]
    assert out["events"][0]["type"] == "promotion"
    assert out["result"]["verdict"] == "answered"


def test_trace_is_persisted_locally_as_jsonl():
    t = trace.begin("t4", "persist me")
    t.finish({})
    trace.end()
    p = Path(os.environ["TWHYNE_TRACE_LOG"])
    assert p.exists()
    recs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    assert any(r["task_id"] == "t4" for r in recs)
    assert trace.read_recent(10)[-1]["task_id"] == "t4"


def test_no_current_trace_is_a_safe_noop():
    trace.end()
    trace.stage("routing")            # must not raise
    trace.model_call("n", {}, 1.0)
    trace.note(level="K")
    assert trace.current() is None


def test_query_response_carries_trace_end_to_end():
    """Through the real Flask app: a deterministic math query (no model)
    must come back with a trace attached by the after_request hook."""
    stub = types.ModuleType("llama_cpp"); stub.Llama = object
    sys.modules.setdefault("llama_cpp", stub)
    os.environ.setdefault("TWHYNE_AUDIT_LOG", os.path.join(tempfile.mkdtemp(), "audit.jsonl"))
    import server
    app = server.create_app()
    c = app.test_client()
    r = c.post("/query", json={"prompt": "What is 715 * 11?", "client_request_id": "bench-1"})
    d = r.get_json()
    assert r.status_code == 200, d
    assert "7865" in (d.get("response") or "")
    tr = d.get("trace")
    assert tr and tr["task_id"] == "bench-1" and tr["mode"] == "current"
    assert tr["neural_calls"] == 0                 # SymPy: zero model time
    assert "tool_s" in tr["segments"] or "router_s" in tr["segments"]
    assert tr["cpu_s"] is not None and tr["rss_mb"] is not None
    # condition A endpoint exists and is traced even when the model is absent
    r2 = c.post("/query/plain", json={"prompt": "hello", "client_request_id": "bench-2"})
    assert r2.status_code in (200, 503)
    assert (r2.get_json() or {}).get("trace", {}).get("mode") == "plain"


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
