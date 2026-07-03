# Hardening roadmap (live-testing backlog)

Priority order, from first live-test review (2026-07-03):

1. **Move secrets to environment variables** - IN PROGRESS: license-signing
   secret now reads from `TWHYNE_LICENSE_SECRET` on the API (default keeps
   existing hashes valid; set the env var in Vercel and rotate when ready).
2. **Replace Flask dev server with production WSGI** (waitress or gunicorn
   inside the container).
3. **Streaming or visible progress states** ("retrieving docs", "generating",
   "executing code", "verifying") - biggest UX gap.
4. **Harden code execution**: memory cap, filesystem isolation, no network by
   default, limited imports (currently: subprocess isolation + 10s timeout).
5. **Improve PDF parsing**: layout-aware extraction, tables, scanned docs,
   chunk provenance.
6. **Expand benchmark to 100-300 tasks**, drawn from the target vertical.
7. **Adversarial RAG tests**: prompt injection inside documents, citation
   mismatch, missing-answer refusal, conflicting sources.
8. **Model/license checksums in the registry** so users know exactly which
   model file is loaded.
9. **Decide whether Planner is real** or remove it from the pitch until it
   has evals.
10. **Mark Vision as experimental** until it has real evals.

Fixed already during live testing:
- Unicode math operators / thousands separators ("47 × 8,912") routed to the
  LLM instead of SymPy and produced wrong arithmetic.
