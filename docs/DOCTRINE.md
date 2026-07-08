# The Twhyne Doctrine (No Slop Standard)

Twhyne is a fail-closed AI system for regulated and high-trust environments.
It computes when possible, cites when grounded, executes and tests when
coding, enforces permissions before retrieval, logs provenance, and refuses
when the available evidence is insufficient.

**A Twhyne answer is either proven, permissioned, labeled, or refused.
Nothing else gets through.**

Twhyne is built for environments where a fluent wrong answer is worse than
no answer.

## The standard

- No answer without provenance.
- No "verified" label without verification actually having run.
- No citation without direct support for the specific claim.
- No tool failure silently dressed up as a response.
- No source access without permission.
- No stale snapshot without a staleness warning.
- No model fallback for deterministic tasks (math is computed, never guessed;
  code is executed, never assumed).
- No action without policy and audit.
- No unsupported confidence. Inference is labeled as inference.
- No fake passes: in evaluation, a runtime error is a failure, always.

## What this means in the code today

| Guarantee | Mechanism (implemented) |
|---|---|
| Math is computed | SymPy short-circuit before any model; normalization for unicode/word operators |
| Code is executed | Sandboxed subprocess + self-generated assert tests; honest two-tier labels |
| Documents are cited | Semantic retrieval, 0.60 grounding threshold, source names in answers, refusal when absent |
| Injection resistance | Grounded prompt constrains to sources; adversarial benchmark case (embedded injection must not fire) |
| Requests are bound | client_request_id end to end; cancelled/stale output discarded, queued jobs skipped |
| Evaluation is honest | Publish-gated CI (image must answer correctly before shipping); errors auto-fail; every live failure becomes a regression test |

## Claims discipline

Say: corruption-resistant, tamper-evident, permissioned, fail-closed,
auditable. Never say: "incorruptible", "enterprise-ready", or
"hospital-ready" until the certification work exists.

Hospital positioning is policy, procedure, compliance, IT operations,
training, documentation and administrative decision support - NOT diagnosis,
treatment, or patient-specific clinical advice (that is the FDA CDS/device
path, taken deliberately or not at all).
