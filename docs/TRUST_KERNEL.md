# Twhyne Trust Kernel — status & roadmap

Twhyne's durable moat is not the model; it is the enforcement layer around it:
**no model sees what it is not authorized to see, no answer leaves without a
verdict, no source is cited unless it supports the claim, and every exchange
is auditable.** Models are replaceable; the Trust Kernel persists.

## Enforcement pipeline (per query)

```
identity/role → authorized source set → retrieve only allowed docs/chunks
→ compute / extract / generate → verify → redact (backstop) → label → audit
```

## Layer status

| Layer | Status |
|------|--------|
| 0  Local / on-prem only (no data leaves) | **done** — structural |
| 1  Role binding on every query | **done** — `role`, default `public` |
| 2  Document-level permissions (per-source ACL) | **done** — `permissions.json` |
| 3  Chunk-level ACL (`[[ROLES: ...]]` overrides its document) | **done** |
| 4  Permission-before-retrieval (unauthorized docs never scored) | **done** |
| 5  Source conflict / currentness resolver | partial (supersession-aware) |
| 6  Output-side secret veto (redaction backstop) | **done** — two-layer |
| 7  Immutable audit ledger (tamper-evident, hash-chained) | **done** |
| 8  Signed identity (verify *who* the role belongs to) | **roadmap** |
| 9  Tool / action policy engine | **roadmap** |
| 10 Adversarial governance benchmark (312 tasks) | **done** |
| 10b Security alerts + human escalation (webhook/email, throttled, opt-in) | **done** |
| 11 External security review / certification | **roadmap** |

## What "done" honestly means here

- **Provable denial.** An unauthorized role never retrieves the restricted
  document or chunk — verified in the benchmark (`perm*` tasks) and unit tests.
- **Tamper-evident audit**, not tamper-proof. Each record's hash chains to the
  previous; altering any past record breaks the chain from that point, and
  `/api/audit/verify` detects it. It proves *whether* the log was altered — it
  does not prevent someone with disk access from rewriting the whole file
  (that needs signed/append-only storage — see below).

## Roadmap — the honest gaps

1. **Signed identity.** Today a caller asserts its own `role`. Real security
   binds the role to a verified identity (JWT / mTLS / SSO), so a client can't
   simply claim `admin`. This is the highest-value next security build.
2. **Cryptographically signed audit records** + append-only/WORM storage, so
   the ledger is tamper-*resistant*, not only tamper-*evident*.
3. **Tool/action policy engine** — govern not just what is *said* but what is
   *done* (writes, external calls).
4. **Node protocol / local mesh (Gen 4).** People, documents, tools, models and
   devices become permissioned nodes that exchange *typed, authorized* messages
   through the kernel — never free-form. Nodes do **not** talk to each other
   today; all coordination is inside one process. This is the long-horizon
   architecture, not a near-term claim.

## Governed adaptation (Gen 3, post-signed-identity)

The thesis. The industry's false tradeoff is *static + controllable* OR
*adaptive + unpredictable*. Twhyne's bet is the fifth option: **adaptive +
evidence-constrained + permission-constrained + auditable + reversible.**
That single principle serves both halves of the product - it is the
intelligence story and the trust story at once.

Precise diagnosis (not "Twhyne has no cognition"): Twhyne's runtime
reasoning and verification loops are the system's own; its **cross-episode
learning is currently human-mediated** - the benchmark -> autopsy -> fix ->
rerun cycle carries improvement across episodes, and the human is the
learning mechanism. The Gen-3 objective is exact: *move selected
cross-episode learning from the developer into the system without
transferring authority to the system.*

Invariants (hold for every item below):
- **Only verified outcomes update anything.** A verified outcome is a
  production result confirmed by an independent deterministic verifier, or
  an authenticated human review with a reproduced failure - not raw user
  interaction. Poisoning-resistant without going blind to the real
  environment.
- **The ledger is the substrate, not the memory.** Never mutate it.
  Immutable ledger -> episodic index -> consolidation -> proposed knowledge;
  raw evidence stays pristine.
- **Learning cannot override a permission.** Adaptations are attributable,
  tested, authorized, versioned, and reversible - the change process itself
  is governed, not just the model's outputs.

Ordered, each gated on the layer before it:

1. **EvaluationRecord** - a general outcome object
   `{claim, expected, observed, verifier, verdict, confidence, error_type,
   evidence}`; prediction-error is one subtype. Attached only where a
   falsifiable expectation exists (code execution, routing), not forced
   onto every answer.
2. **Conditional node reliability profiles** (the first genuinely adaptive
   capability). NOT global accuracy. The unit is
   `NodeCapabilityProfile{node, task_family, conditions, verified_accuracy,
   abstention_rate, false_confidence_rate, latency, evidence}`. Routing
   becomes: task requirements + authorization + conditional reliability +
   cost -> route. The router forms an empirical self-model of its own
   components - a real self-model, no mysticism.
3. **Human-gated consolidation** - ledger -> pattern miner (recurring
   failure / route / evidence conflict / abstention) -> proposed rule ->
   validation (benchmark simulation + regression + confidence threshold) ->
   human approval -> active rule, with origin, evidence, approver, version,
   and rollback. The learning process is itself governed - arguably Twhyne's
   most distinctive idea.
4. **Governed state registry** (the world-model idea, Twhyne-sized). The
   research problem with world models is getting state that is learned AND
   grounded; symbolic state is "brittle" - but a governed corpus is closed,
   small, and observable, where brittleness is called correctness. Build an
   explicit, queryable state extracted from verified sources with
   provenance: entities (policies, sources, roles), facts with effective
   dates, supersession/conflict edges. Enforced at the answer choke point
   like every other gate, so the model cannot skip it ("policy consults the
   state" by architecture, not training). Payoff: "model asserted X, state
   says not-X" becomes a checkable inconsistency - hallucination as a
   detectable failure class - plus queryable supersession and temporal
   answers. Stage it as a VERIFIER (flag inconsistencies, strengthen
   refusals) before ever making it a hard bottleneck. Facts enter state only
   via verified extraction with human promotion; the ledger remains the
   untouched substrate.
5. **Learned latent world models / open-world experimentation** - not ours
   to build; that is frontier-lab work on frontier-lab compute. The
   replaceable-node architecture absorbs such models when they ship as
   runnable artifacts, the same way Qwen replaced CodeLlama. Robotics and
   sensor-fusion examples remain a different product; pursuing them now is
   mission creep.

Gen 3 is not AGI. It is a system that gets empirically better at using its
own components from verified experience, while preserving evidence,
authorization, human control, and a complete history of why it changed.

## Claims discipline

Say: *"permission-first retrieval, two-layer redaction, tamper-evident audit,
demonstrated on a published adversarial benchmark."*
Do **not** say: *"cannot leak," "incorruptible," or "enterprise-secure"* until
signed identity, signed audit, and an external review exist.

On differentiation, do **not** claim *"no cloud provider can match this"* -
it is absolute and probably false (a provider could architect the same
properties). The defensible claim is the design principle: **Twhyne treats
authority, evidence, and learning as governed system properties rather than
capabilities entrusted to a foundation model.** The question is whether
Twhyne does this foundationally - not whether others could.
