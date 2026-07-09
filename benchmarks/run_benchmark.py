#!/usr/bin/env python3
"""Twhyne benchmark harness (stdlib only).

Sends real tasks through the RUNNING backend (default http://localhost:5002),
scores each answer with a task-appropriate checker, and prints a per-category
summary. Optionally compares against a cloud model for win/tie/loss.

Start the Twhyne app first, then run this. No pip installs required.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS_FILE = HERE / "tasks.json"
CORPUS_DIR = HERE / "corpus"


def _post(url, payload, timeout=600):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _get(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ---- scoring helpers -------------------------------------------------------

def _numbers(text):
    """All integer-ish numbers in text, commas stripped."""
    return {n.replace(",", "") for n in re.findall(r"-?[\d,]*\d", text)}


def score_math(task, answer, sources):
    want = str(task["expect_number"]).replace(",", "")
    return want in _numbers(answer), f"expected number {want}"


def score_grounded(task, answer, sources):
    low = answer.lower()
    reasons = []
    ok = True
    for s in task.get("expect_contains", []):
        if s.lower() not in low:
            ok = False; reasons.append(f"missing '{s}'")
    anys = task.get("expect_any", [])
    if anys and not any(a.lower() in low for a in anys):
        ok = False; reasons.append(f"none of {anys}")
    for s in task.get("must_not_contain", []):
        if s.lower() in low:
            ok = False; reasons.append(f"hallucination '{s}' present")
    cite = task.get("must_cite")
    if cite:
        cited = any(cite.lower() in str(x).lower() for x in (sources or []))
        # fall back to citation embedded in the answer text
        cited = cited or (cite.lower() in low)
        if not cited:
            ok = False; reasons.append(f"did not cite '{cite}'")
    return ok, "; ".join(reasons) or "all checks passed"


def score_contains(task, answer, sources):
    low = answer.lower()
    reasons = []
    ok = True
    for s in task.get("expect_all", []):
        if s.lower() not in low:
            ok = False; reasons.append(f"missing '{s}'")
    anys = task.get("expect_any", [])
    if anys and not any(a.lower() in low for a in anys):
        ok = False; reasons.append(f"none of {anys}")
    return ok, "; ".join(reasons) or "all checks passed"


_CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*(.*?)```", re.S)


def score_code(task, answer, sources):
    """Code tasks must pass EXTERNAL unit tests, not just self-generated ones.

    The extracted code block is executed in an isolated subprocess with the
    task's `unit_tests` asserts appended. Self-tests once let a logically
    wrong FizzBuzz (15 -> 'Fizz') and TODO stubs count as passes.
    """
    ok, reasons = score_contains(task, answer, sources)
    m = _CODE_BLOCK_RE.search(answer)
    if not m:
        return False, "no code block in answer"
    code = m.group(1).strip()
    tests = task.get("unit_tests", [])
    if tests:
        program = code + "\n\n" + "\n".join(tests) + "\n"
        try:
            proc = subprocess.run([sys.executable, "-I", "-c", program],
                                  capture_output=True, text=True, timeout=15)
            if proc.returncode != 0:
                err = (proc.stderr or "nonzero exit").strip().splitlines()[-1][:200]
                return False, f"external unit tests FAILED: {err}"
        except subprocess.TimeoutExpired:
            return False, "external unit tests timed out"
    if not ok:
        return False, reasons
    return True, "external unit tests passed" if tests else "all checks passed"


# Any of these in a final answer is slop by definition: error text, failed
# verification, tracebacks, or unfinished TODO stubs must never pass.
_SLOP_MARKERS = ["failed automatic verification", "syntaxerror",
                 "traceback (most recent call last)", "# todo", "[error:"]

# Grading time limits (seconds) per category. Accuracy after 10 minutes is
# still a UX failure; the previous 600s harness timeout was the only bound.
_TIME_LIMITS = {"math": 10, "general": 180, "reasoning": 180,
                "code": 420, "grounded_qa": 300}


SCORERS = {
    "math": score_math,
    "grounded_qa": score_grounded,
    "code": score_code,
    "general": score_contains,
    "reasoning": score_contains,
}


# ---- backend interaction ---------------------------------------------------

def ensure_corpus_dataset(base_url):
    """Create (once) a RAG dataset from corpus/ files. Returns dataset_id."""
    files = []
    for p in sorted(CORPUS_DIR.glob("*")):
        if p.is_file():
            files.append({"filename": p.stem, "content": p.read_text(encoding="utf-8", errors="ignore")})
    if not files:
        return None
    # v2: bump when corpus files change, so a stale dataset from an earlier
    # run is not silently reused without the new documents.
    name = "benchmark-corpus-v2"
    # Reuse if it already exists.
    try:
        existing = _get(base_url + "/api/rag/datasets").get("datasets", [])
        for d in existing:
            if d.get("name") == name:
                return d["id"]
    except Exception:
        pass
    resp = _post(base_url + "/api/rag/datasets",
                 {"name": name, "description": "benchmark corpus", "files": files})
    ds = resp.get("dataset", {})
    return ds.get("id")


def ask_twhyne(base_url, prompt, dataset_id=None, use_rag=False):
    payload = {"prompt": prompt}
    if use_rag and dataset_id:
        payload["dataset_id"] = dataset_id
        payload["use_rag"] = True
    resp = _post(base_url + "/query", payload)
    text = resp.get("response") or resp.get("result") or ""
    return text, resp.get("sources", []), resp.get("node_id", "")


# ---- optional cloud comparison ---------------------------------------------

def ask_cloud(provider, prompt):
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            return None
        body = {"model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read())
        return d["choices"][0]["message"]["content"]
    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return None
        body = {"model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"),
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "x-api-key": key,
                     "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read())
        return "".join(b.get("text", "") for b in d.get("content", []))
    return None


# ---- scripted scenarios ------------------------------------------------------

def run_cancellation_scenario(base):
    """Regression for the live-test failure: abandon a slow request, cancel
    it, then verify the NEXT question gets ITS OWN correct answer (no stale
    output, queued cancelled job skipped)."""
    rid = f"bench-cancel-{int(time.time() * 1000)}"
    try:
        _post(base + "/query", {"prompt": "Explain the history of computing in detail.",
                                "client_request_id": rid}, timeout=1)
    except Exception:
        pass  # abandoned on purpose, like a user hitting Cancel
    try:
        _post(base + "/cancel", {"client_request_id": rid}, timeout=15)
    except Exception as e:
        return False, f"/cancel endpoint failed: {e}"
    try:
        answer, _, _ = ask_twhyne(base, "what is 47 × 8,912?")
    except Exception as e:
        return False, f"follow-up query failed: {e}"
    if "418864" in answer.replace(",", ""):
        return True, "exact answer after cancel"
    return False, f"wrong/stale answer: {answer[:120]}"


# ---- main ------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("TWHYNE_URL", "http://localhost:5002"))
    ap.add_argument("--cloud", choices=["openai", "anthropic"], default=None,
                    help="also run tasks against a cloud model for comparison")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    try:
        _get(base + "/status", timeout=10)
    except Exception as e:
        print(f"ERROR: backend not reachable at {base} ({e}).\n"
              f"Start the Twhyne app first, then re-run.")
        sys.exit(1)

    tasks = json.loads(TASKS_FILE.read_text())
    dataset_id = None
    if any(t.get("use_rag") for cat in tasks.values() for t in cat):
        print("Preparing benchmark RAG corpus...")
        dataset_id = ensure_corpus_dataset(base)
        print(f"  dataset_id = {dataset_id}\n")

    results = []
    cat_stats = {}
    for category, items in tasks.items():
        scorer = SCORERS[category]
        for task in items:
            t0 = time.time()
            try:
                answer, sources, node_id = ask_twhyne(base, task["prompt"],
                                                      dataset_id, task.get("use_rag", False))
            except Exception as e:
                answer, sources, node_id = f"[error: {e}]", [], ""
            elapsed = round(time.time() - t0, 1)
            low = answer.lower()
            slop = next((m for m in _SLOP_MARKERS if m in low), None)
            limit = task.get("time_limit_s", _TIME_LIMITS.get(category))
            if answer.startswith("[error:"):
                # A runtime error is ALWAYS a failure - never let expected
                # strings coincidentally matched inside an error message count
                # as a pass (a WinError code once satisfied a "100" check).
                local_ok, reason = False, "runtime error (auto-fail)"
            elif slop:
                # Slop markers auto-fail: failed verification, tracebacks and
                # TODO stubs in a final answer are never acceptable output.
                local_ok, reason = False, f"slop marker in answer: '{slop}' (auto-fail)"
            else:
                local_ok, reason = scorer(task, answer, sources)
                if local_ok and limit and elapsed > limit:
                    local_ok, reason = False, f"correct but too slow ({elapsed}s > {limit}s limit)"
                want_node = task.get("expect_node")
                if local_ok and want_node and node_id != want_node:
                    local_ok, reason = False, f"misrouted: answered by '{node_id}', expected '{want_node}'"

            cloud_ok = None
            if args.cloud:
                try:
                    c = ask_cloud(args.cloud, task["prompt"])
                    if c is not None:
                        cloud_ok, _ = scorer(task, c, [])
                except Exception:
                    cloud_ok = None

            st = cat_stats.setdefault(category, {"pass": 0, "total": 0,
                                                 "cloud_pass": 0, "cloud_total": 0})
            st["total"] += 1
            st["pass"] += int(local_ok)
            if cloud_ok is not None:
                st["cloud_total"] += 1
                st["cloud_pass"] += int(cloud_ok)

            flag = "PASS" if local_ok else "FAIL"
            extra = ""
            if cloud_ok is not None:
                extra = f"  cloud={'PASS' if cloud_ok else 'FAIL'}"
            print(f"[{flag}] {category}/{task['id']} ({elapsed}s){extra}  {reason}")
            if not local_ok:
                print(f"        answer: {answer[:200].replace(chr(10), ' ')}")
            results.append({"category": category, "id": task["id"],
                            "prompt": task["prompt"], "local_pass": local_ok,
                            "cloud_pass": cloud_ok, "reason": reason,
                            "elapsed_s": elapsed, "node_id": node_id,
                            "answer": answer, "sources": sources})

    # Scripted scenario: cancellation must not poison the next answer.
    t0 = time.time()
    ok, reason = run_cancellation_scenario(base)
    st = cat_stats.setdefault("scenarios", {"pass": 0, "total": 0,
                                            "cloud_pass": 0, "cloud_total": 0})
    st["total"] += 1
    st["pass"] += int(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] scenarios/cancel_stale ({round(time.time()-t0,1)}s)  {reason}")
    results.append({"category": "scenarios", "id": "cancel_stale",
                    "prompt": "(cancel mid-flight, then unrelated question)",
                    "local_pass": ok, "cloud_pass": None, "reason": reason,
                    "elapsed_s": round(time.time()-t0, 1), "answer": "", "sources": []})

    print("\n" + "=" * 60)
    print(" SUMMARY")
    print("=" * 60)
    tot_p = tot_t = 0
    for cat, st in cat_stats.items():
        tot_p += st["pass"]; tot_t += st["total"]
        line = f"  {cat:14s} {st['pass']}/{st['total']} local"
        if st["cloud_total"]:
            line += f"   vs cloud {st['cloud_pass']}/{st['cloud_total']}"
        print(line)
    print("-" * 60)
    print(f"  {'TOTAL':14s} {tot_p}/{tot_t} local  ({round(100*tot_p/max(tot_t,1))}%)")

    out = HERE / "results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nDetailed results written to {out}")


if __name__ == "__main__":
    main()
