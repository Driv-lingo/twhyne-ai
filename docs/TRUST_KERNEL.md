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

## Cognitive roadmap (post-signed-identity)

Twhyne already runs a cognitive loop offline: the adversarial benchmark ->
failure autopsy -> fix -> rerun cycle is observe/predict/verify/learn with a
human as the consolidation step, and the audit ledger is persistent episodic
memory (every question, verdict, evidence hash, outcome). The cognitive work
is moving that loop toward runtime WITHOUT letting learning escape the
security boundaries - learned behavior can never override a permission, and
nothing consolidates into knowledge without verification.

Ordered, each gated on the layer before it:

1. **Prediction records** - executed answers carry predicted vs observed
   outcome and prediction_error in the gates (the code node already does
   this implicitly; make it explicit and auditable).
2. **Node reliability profiles** - benchmark history mined into per-node,
   per-category accuracy/latency profiles consulted by the router. The
   learning signal is verified benchmark evidence only, never raw user
   interaction - poisoning-resistant by construction.
3. **Episodic consolidation, human-gated** - mine the audit ledger for
   recurring verified patterns; surface as PROPOSED rules in the admin
   console for a person to promote. No autonomous self-modification.
4. **World-state modeling / active experimentation** - parked until a
   customer use case requires state tracking; recorded so it is not lost.

Definition we build toward (and the only "intelligence" claim we make):
*verified adaptive model-building* - how efficiently the system constructs
an accurate model of something unfamiliar, detects when it is wrong, and
improves, with every update authorized, attributable and auditable.

## Claims discipline

Say: *"permission-first retrieval, two-layer redaction, tamper-evident audit,
demonstrated on a published adversarial benchmark."*
Do **not** say: *"cannot leak," "incorruptible," or "enterprise-secure"* until
signed identity, signed audit, and an external review exist.
