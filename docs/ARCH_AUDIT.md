# Architecture audit — baseline before the cognitive-work iteration

**Scope:** phase 1 of the WDA/WCA implementation contract. Facts below are
measured or read from the code on `pre-prod` @ `8020559`; nothing here is a
projection. This is the regression floor the new architecture must not
lower.

## Regression baseline (measured, this commit)

| Check | Result |
|---|---|
| `backend/verify.py` (evidence 21, live-fetch 12, math suite, 5 smoke checks) | **all pass** |
| `pytest backend/tests/` | **53 passed** in 0.5s |
| Benchmark harness (`benchmarks/run_benchmark.py`, 312 tasks) | last operator run: 95.5% local pass (see `docs/`/site); **not re-run here** — requires a running model |

Deps for offline tests: `flask flask-cors sympy pytest numpy` with `llama_cpp`
stubbed (`verify.py` does this itself). No model, Docker, or network needed.

## What exists (reuse, do not duplicate)

### Runtime (`backend/server.py`, 3360 lines, 37 routes)
The `/query` path in `submit_query` is already an *implicit* tiered router.
Ordered decision sequence (line refs @ this commit):

1. Deterministic self/timer answers (`_SELF_Q_RE`, `_TIMER_Q_RE`, ~1777–1855) — never reach a model.
2. **DETERMINISTIC TOOLS FIRST** (1932): `_looks_like_math` → SymPy node, lock-free.
3. **SPECIALIST SHORTCUT** (1956–2058): keyword scoring `_route_query` (438) → code / planner / vision, skipping retrieval.
4. **RETRIEVAL-FIRST** (2060): answer cache (`_ANSWER_CACHE`, 256 entries, keyed on prompt+dataset+role+store version) → `_retrieve` (1402) → auto-grounding veto (lexical overlap) → **extractive** answer (`_extractive_answer`, 199) → grounded language generation.
5. Ungrounded specialist fallback (2412) → `node.process`.
6. **Choke point** `_redact_response` (1493, `after_request`): stale-source labelling, quantity-conservation withhold (`_arith_consistency`, 1449), secret redaction. Every `/query` response passes through it — the natural single place to attach a trace.

Existing "competency-like" mechanisms, all deterministic and already
verified-on-use:
- SymPy math node with worked steps (`flux_nodes/math.py`).
- Code library: 36 executed-and-tested snippets, `code_library.match()` (713 lines).
- Extractive QA: quotes a source span, no generation.
- Answer cache (exact-prompt replay).

These are the seeds of S-level competencies; they lack a shared schema,
guards, envelopes, provenance, cost accounting, or lifecycle.

### Nodes (`flux_nodes/base.py`)
`FluxNode.generate(prompt, **kwargs)` / `process(Query) -> Response`. `Query`
carries `parameters` (already threads `client_request_id` for cancellation).
`shared_model.py`: single-resident llama.cpp model, `INFER_LOCK`, per-token
cancellation, tok/s logging. **No token/TTFT data is returned to callers.**

### Retrieval / permissions (`rag_manager.py`)
`SemanticRAGManager`: `search_dataset`, `match_dataset`, chunk-level ACL
(`role_can_access`, `node_can_access`), `action_policy`, versioned store
(`version()`), `permissions.json` policy incl. verification + action policy.
Permission-before-retrieval is enforced here; the new state layer must sit
*behind* it, never bypass it.

### Persistent local state (`rag_storage/`, mounted volume)
`audit_ledger.jsonl` (hash-chained, `_audit_append` 612), `conversations.json`,
`permissions.json`, datasets + embeddings, `evidence_store/`, `license_state.json`.
All local; no cloud state. New WDA / belief / competency stores go here.

### Verification today
Deterministic where it exists: SymPy exactness, code execution + user-example
asserts (`code.py`), arithmetic conservation, extractive spans, redaction.
Generic "LLM checks LLM" is **not** used. There is no separation of
groundedness / logical validity / applicability / utility — one verdict.

### Benchmark harness (`benchmarks/run_benchmark.py`)
Drives `/query` over `tasks.json` (dict: category → task list; categories
math 120, general 60, grounded_qa 50, reasoning 40, code 30, permissions 12,
scenarios 1). Per-category scorers (`score_math/grounded/contains/code`),
slop-marker auto-fail, latency limits, `expect_node` routing checks, cancel
scenario, optional cloud comparison. Result schema per task: `category, id,
prompt, local_pass, correct, latency_ok, cloud_pass, reason, elapsed_s,
node_id, answer, sources, gates, evidence`. **Measures wall time only** — no
tokens, model calls, TTFT, CPU, RAM, or routing cost.

### Instrumentation today
`_set_progress(state, detail)` marks stages (routing / retrieving /
queued / generating / computing) for the UI poll; tok/s is *logged*, not
returned. Nothing per-task is persisted for analysis.

## Gaps against the contract (what phase 2+ must add)

| Contract item | Status now |
|---|---|
| Persistent actor-independent WDA domain state, incremental update | absent (RAG chunks are text, not a domain model) |
| World / system-belief / actor-belief / task-goal separation | absent |
| Query-relevant state reduction W→W* | absent (retrieval does top-k text only) |
| Hierarchical Goal→Subgoal→Method→Operator | absent (planner node is free text) |
| SOCA cheapest-adequate allocation | implicit, hard-coded order in `submit_query` |
| K/R/S levels, reversible | absent; deterministic tools are un-levelled |
| Competency object, induction, promotion/demotion, versioning | absent |
| Two independent guards (formal + semantic) | absent; keyword scores gate specialists |
| Tiered router with per-tier cost | implicit, uninstrumented |
| Decision relevance / EIG for ambiguity | absent |
| Verification dimensions V_G/V_L/V_A/V_U | single verdict |
| Per-task trace (tokens, TTFT, times, CPU/RAM, level, guards) | absent |
| A/B/C/D same-hardware harness + NDR/CCR/break-even | absent (single-mode harness) |
| Five workload types + distribution shift | absent (categories are by domain, not by structure) |

## Reuse plan (binding for later phases)
- Keep `submit_query`'s working behaviour as condition **B** unchanged; add a
  `mode` switch so A/C/D are the same process with layers toggled.
- Attach traces in `_redact_response` (one hook covers all 20+ return sites).
- Wrap, don't replace, `FluxNode.generate` to capture model-call metrics.
- Promote SymPy / code library / extractive QA into first-class competencies
  behind the Competency schema rather than rewriting them.
- Extend `run_benchmark.py` (add `--mode`, trace capture) and add a separate
  workload generator + report; never fork the runner.

## Migration notes
- No schema changes to existing stores. New stores are additive files under
  `rag_storage/` (`wda.json`, `beliefs.json`, `competencies.json`,
  `task_traces.jsonl`) — local only, covered by the same volume/backup.
- All new layers default **off** except tracing (which is read-only
  instrumentation), so a user on the current image sees no behavioural change
  until conditions C/D are enabled.
- Constraints honoured: no cloud inference/embeddings/state/verification, no
  new egress, GPU optional, single cognitive system (modules, not agents).

## Known limitations of this baseline
- TTFT cannot be measured on the non-streaming llama.cpp path; until
  streaming lands it will be reported as `null`, never estimated.
- Energy is not exposed by the Docker Desktop VM; reported as unavailable.
- The 312-task pass rate above was operator-measured on their hardware; this
  container has no model, so architecture comparisons must be run on the
  same machine as before.
