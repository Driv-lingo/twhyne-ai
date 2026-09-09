# Cognitive-work layer — schemas, interfaces, modes, migration

Implements the WDA/WCA architecture contract incrementally on top of the
existing runtime. Everything is local (JSON under `rag_storage/`), nothing
requires a GPU, nothing leaves the machine. One cognitive system with
modules — not agents.

## Modes (the A/B/C/D conditions)

Selected per request (`"mode"` in the `/query` body) or by `TWHYNE_MODE`.

| mode | condition | what runs |
|---|---|---|
| `plain` | **A** | `/query/plain`: bare language model. No shortcuts, retrieval, cache, routing or competencies. Choke point still applies. |
| `current` | **B** | today's pipeline, unchanged. Cognition layer inert (traces only). |
| `structured` | **C** | B + post-K verification dimensions (V_G/V_L/V_A/V_U), state schemas, router selection is *measured* but competencies are never induced or executed. |
| `full` | **D** | C + K→R→S maturation: induction from verified K answers, evidence/economics-gated promotion, Tier-0 execution behind two guards, demotion/invalidation. |

The C-vs-D difference is exactly and only the learning loop; both have the
same operator templates available as verifiers.

## Modules (`backend/cognition/`)

- `trace.py` — one `TaskTrace` per `/query`: level (K/R/S), tier, candidates, selected competency + why, guard results, escalation, every neural call (tokens, gen time, tok/s), segment times (router / retrieval / queue / generation / verification / tool), CPU s, RSS, verdict. Returned as `trace` on the response and appended to `rag_storage/task_traces.jsonl`. Unmeasured = `null`, never estimated (TTFT on non-streaming path, energy, GPU on CPU image).
- `state.py` —
  - `WorkDomainModel` (**W_t**): persistent, actor-independent WDA nodes (kind ∈ purpose/value/constraint/function/process/resource/relationship/entity; level ∈ purpose/value/function/process/resource; decomposition `parent`; `relations`; `provenance`; per-node `version`/`updated_at`; `valid_until`). `update(delta)` is incremental — only named nodes change. Observer-relative keys are **rejected**. `reduce(query, max_nodes)` → **W\*** bounded slice. `decomposition_path(id)` is the hierarchical index key.
  - `BeliefStore` (**B_T**, **B_i**): per-observer factorised alternatives with weight, evidence, source, timestamp, uncertainty class (semantic/perceptual/epistemic/stochastic), dependencies. `disagreements(key, world_value)` exposes W vs B_T vs B_i conflicts.
  - `TaskState` (**G_t**, CTA): goal, current, W\*, constraints, unresolved variables, decisions, consequence_of_error, transitions, hierarchical subgoals (Goal→Subgoal→Method→Operator).
  - `decision_relevance(alternatives, action_for)` + `resolve_or_escalate(...)`: ambiguity is resolved only when alternatives imply different actions; EIG from minority weight; consequence-aware act / caveat / clarify.
  - `DomainIndex`: structural-first index by decomposition path (exact / prefix / signature). Similarity never establishes applicability.
- `competency.py` — `Competency` (full field list in the class), `Envelope`, `CompetencyLibrary` (promotion/demotion/refine/invalidate/conflicts/specificity), `PromotionPolicy` (configurable; env `TWHYNE_PROMOTE_R`, `TWHYNE_PROMOTE_S`, `TWHYNE_EV_RATIO`), `expected_value(...)`, `task_features(prompt)`. Registries `EXECUTORS/PARSERS/SEMANTIC_GUARDS/VERIFIERS` — behaviour is code, referenced by name.
- `operators.py` — operator templates and `fit_templates(prompt, number)` (which known formula reproduces a K answer), `extract_number`, `all_parses`. Each template: parser, executor, semantic guard, verifier, envelope, counterexample perturbations.
- `controller.py` — `Controller.select` (Tier 0), `.execute` (R: full verification = postconditions + independent re-derivation; S: light), `.post_k` (verification dims; induction in `full`), `.induce` (trace → parameterised template → examples → replay → generated counterexamples both guards must reject → candidate → `consider_promotion`), `.report_outcome`.
- `runtime.py` — process singletons; `mode_active(mode)`.

## Router tiers (each timed into `trace.segments`)

0. exact/structural competency match (parser + formal guard + semantic guard) — D only executes
1. symbolic/rule/state (existing SymPy math, timers, self-answers, extractive QA)
2. cheap semantic routing (existing keyword scoring; candidates only)
3. full neural reasoning (existing pipeline) → post-K verification (+ induction in D)

## Lifecycle

`candidate → R → S`, reversible: any failure, counterexample, guard disagreement, stale dependency, conflict or envelope violation moves **down**; an unexplained wrong answer **invalidates** (candidate + stale) — never efficiently wrong. Promotion requires `min_successes` **and** `EV/cost ≥ ratio` with EV from *measured* K-baseline cost vs measured own latency + verification. Rare/low-savings work stays K by design.

## Storage (all local, additive, under the mounted `rag_storage/`)

`task_traces.jsonl`, `wda.json`, `beliefs.json`, `competencies.json`. No existing store changes. Override the directory with `TWHYNE_STATE_DIR` (tests) and the trace file with `TWHYNE_TRACE_LOG`.

## Running the experiment (same machine, same model)

```
cd benchmarks
python generate_workloads.py                      # workloads.json (deterministic ground truth)
python run_benchmark.py --mode plain      --tasks workloads.json --out results-A.json
python run_benchmark.py --mode current    --tasks workloads.json --out results-B.json
python run_benchmark.py --mode structured --tasks workloads.json --out results-C.json
python run_benchmark.py --mode full       --tasks workloads.json --out results-D.json
python report.py --run A=results-A.json --run B=results-B.json --run C=results-C.json --run D=results-D.json
```
Condition D must run on a **fresh** `competencies.json` (delete it first) so
maturation is measured from zero. `report.py` prints accuracy, success,
latency, tokens, model calls, CPU, RSS, router/verify overhead, K/R/S mix,
NDR and NDR(n) per family, CCR, cost per success, FP activation, FN
escalation, OOD recall, promotions/rollbacks, and break-even n\* (C vs D).

## Migration notes

- Default behaviour is unchanged (`current`). Users see nothing new unless a
  mode is set.
- Enabling `full` for real use should wait for the benchmark: it is the
  hypothesis under test, not a shipped feature.
- Rolling back = removing the four new files; no schema migration exists to
  undo.

## Known limitations (honest)

- Induction is grounded in operator **templates** (deterministic formulas the
  system can re-derive). It does not yet induce brand-new operators from
  free-form LLM reasoning; a K answer with no reproducing template stays K
  and is labelled `V_L: unverified`.
- Semantic guards are cue-based (lexical), not a learned verifier.
- Composition (`pct_then_div`, `discount_then_tax`) is template-level;
  automatic composition of arbitrary learned operators is not implemented.
- Decision-relevance machinery exists in `state.py` but is not yet wired into
  the ambiguous-workload answers.
- TTFT and energy are not measured on this build.
