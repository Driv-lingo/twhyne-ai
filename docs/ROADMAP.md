# Roadmap: Strict Mode v1

Goal: **a 300-task regulated-domain benchmark with zero fake passes, zero
stale answers, exact citations, claim verification, permission-aware
retrieval, and fail-closed runtime behavior.** The larger vision (permissioned
distributed intelligence) earns credibility only through this milestone.

## Now (stability + honesty)

1. **Diagnose the code-path crash** from the exhaustive run (launchers now
   keep the container so `docker logs twhyne-ai` survives; reproduce and fix).
2. ~~Errors are never passes~~ - DONE (benchmark auto-fails runtime errors).
3. ~~Math natural-language routing~~ - DONE (unicode, commas, times/multiplied
   by; regression-tested).
4. ~~Hard cancellation~~ - DONE (request ids end to end, queued jobs skipped).
5. ~~Production WSGI~~ - DONE (waitress). ~~Progress states~~ - DONE.
6. ~~Secrets to env vars~~ - DONE (TWHYNE_LICENSE_SECRET; rotate in Vercel).

## Next (strictness upgrades, in order)

7. **Strict mode flag**: only computed / cited / executed-and-tested /
   refused outputs allowed; unverified model prose is labeled or suppressed.
8. **Exact citation spans**: section/chunk/sentence + content hash instead of
   document-level "Sources:" lines.
9. **Claim-level verifier**: split answers into factual claims; each claim
   needs a supporting span, a computation, or removal.
10. **Permission-before-retrieval**: identity/role -> allowed corpus ->
    retrieve; never retrieve-then-redact. Node trust tiers.
11. **Tamper-evident audit log**: append-only, hash-chained record per answer
    (who/when/node/sources used and blocked/policy/trust label/versions).
12. **Source/model/index versioning + checksums** in the registry; staleness
    labels on old snapshots.
13. **Harden code execution**: memory cap, no network, filesystem isolation
    (today: subprocess isolation + 10s timeout).
14. **Conflict detection**: contradictory sources surfaced, not averaged.

## Evaluation (the proof)

15. **300-task benchmark** structured around failure modes: answerable /
    not-in-source / conflicting-source / outdated-policy /
    permission-restricted / injection-inside-document / table+PDF layout /
    multi-document synthesis. Hybrid retrieval (BM25 + embeddings + rerank)
    evaluated separately from answer faithfulness.
16. **Compliance mapping**: behavior mapped to NIST AI RMF + GenAI profile,
    NIST SP 800-53 controls, HIPAA Security Rule safeguards; FedRAMP pathway
    if a hosted tier ever exists.

## Also tracked

- Improve PDF parsing (layout, tables, scanned docs, chunk provenance).
- Streaming tokens (progress states shipped; token streaming later).
- Reasoning-distill node (R1-class) via the model registry.
- Decide Planner honestly; mark Vision experimental until it has evals.
- Mesh phase 1 (one box, many clients) after a paying/pilot user exists.

## Positioning while building

Controlled reveal, not launch: technical preview for 3-5 reviewers/pilots.
Demo the narrow wedge - local source-grounded policy & operations
intelligence with refusal excellence - not "Web4". See docs/DOCTRINE.md for
the language discipline.
