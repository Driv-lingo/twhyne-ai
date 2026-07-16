#!/usr/bin/env python3
"""One-command verification of everything machine-testable in this build.

    cd backend && python3 verify.py

Runs the offline unit suites (math routing, evidence broker freeze-layer)
plus fast smoke checks of the deterministic logic that changed recently -
arithmetic-conservation, code library, name matching, timers. Needs only
Python 3 + the repo's test deps (pytest optional); no Docker, no models, no
network. Exits non-zero if anything fails, so it doubles as a CI gate.

For the parts a machine cannot judge (generation quality, real inference
speed, the chat UI), see docs/TEST_CHECKLIST.md.
"""
import importlib.util
import os
import subprocess
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

# Stub llama_cpp so server.py imports without the native engine / model files.
_stub = types.ModuleType("llama_cpp")
_stub.Llama = object
sys.modules.setdefault("llama_cpp", _stub)
os.environ.setdefault("TWHYNE_AUDIT_LOG", "/tmp/twhyne_verify_audit.jsonl")

results = []  # (name, ok, detail)


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail and not ok else ""))


def run_file_suite(path, label):
    """Run a standalone test file (they self-run via __main__ and exit-code)."""
    r = subprocess.run([sys.executable, path], capture_output=True, text=True)
    tail = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
    record(label, r.returncode == 0, tail if r.returncode else tail)


def main():
    print("=" * 60)
    print(" TWHYNE VERIFICATION")
    print("=" * 60)

    # 1) Standalone unit suites
    run_file_suite("tests/test_evidence.py", "Evidence broker suite (21 tests)")
    run_file_suite("tests/test_math_node.py", "Math node suite")

    # 2) Deterministic logic smoke checks (import the real code paths)
    import server  # noqa
    app = server.create_app()
    c = app.test_client()

    # arithmetic conservation: the apple failure must be withheld
    j = c.post("/query", json={
        "prompt": "If sally has 2 apples and johnny has 3 but split it 7 ways?"})
    # (no model, so the language node errors; we only check the checker fires
    #  via a direct call to be model-independent)
    with app.test_request_context("/query", method="POST", json={
            "prompt": "sally has 2 apples and johnny has 3, split 7 ways"}):
        import flask
        r = flask.jsonify({"response": "a total of seven apples", "result": "x",
                           "grounded": False, "node_id": "language-mistral-7b"})
        import json as _j
        d = _j.loads(app.process_response(r).get_data())
    record("Arithmetic conservation withholds impossible answer",
           d.get("quantity_upper_bound_violation") is True
           and "withheld" in d.get("response", ""))

    # code library: classic request is an instant executed hit
    from flux_nodes.code_library import match as lib_match
    hit = lib_match("write a function to reverse a linked list")
    record("Code library matches a classic request",
           bool(hit and hit["name"] == "Reverse a linked list"))
    # ...and every library snippet passes its own tests
    from flux_nodes.code import _verify_code
    from flux_nodes.code_library import LIBRARY
    bad = [e["name"] for e in LIBRARY if not _verify_code(e["code"])[0]]
    record(f"All {len(LIBRARY)} library snippets execute + pass tests",
           not bad, ("failing: " + ", ".join(bad)) if bad else "")

    # KB name matching survives a decorated name
    from rag_manager import get_rag_manager
    rm = get_rag_manager()
    ds = rm.create_dataset("Twhyne Docs", "", [{"filename": "d.txt",
        "content": "Twhyne is a local-first trust kernel. " * 10,
        "encoding": "utf-8"}])
    record("KB name match works on a decorated name",
           rm.match_dataset("tell me about twhyne") == ds["id"])
    rm.delete_dataset(ds["id"])

    # SSRF destination validation core cases
    from evidence.destination import validate_url, validate_resolved_ip
    ssrf_ok = (validate_url("https://visitdubai.com/x", ["visitdubai.com"])[0]
               and not validate_url("https://169.254.169.254/", ["visitdubai.com"])[0]
               and not validate_resolved_ip("127.0.0.1")[0]
               and validate_resolved_ip("93.184.216.34")[0])
    record("SSRF destination validation (allow public, block private/metadata)",
           ssrf_ok)

    print("=" * 60)
    n_ok = sum(1 for _, ok, _ in results if ok)
    print(f" TOTAL: {n_ok}/{len(results)} checks passed")
    print("=" * 60)
    if n_ok != len(results):
        print("\nSee the failing lines above. For app-level and generation-"
              "quality checks a machine can't judge, run docs/TEST_CHECKLIST.md.")
    sys.exit(0 if n_ok == len(results) else 1)


if __name__ == "__main__":
    main()
