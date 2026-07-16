# Twhyne Evidence Broker — Phase 0A (semantics only, NO network).
#
# This package defines the evidence objects, status vocabulary, and the
# deterministic checks that make live-sourced claims trustworthy WITHOUT
# giving Twhyne core an internet route. Phase 0A is pure logic + schemas +
# negative tests; the actual fetch worker, egress proxy, and signing service
# are Phase 0B/1 (see docs/ROADMAP.md, "Evidence Broker").
#
# The four objects are DISTINCT on purpose - collapsing any two recreates a
# trust hole documented in the roadmap:
#   raw_response_record   proxy-owned, immutable (the bytes actually received)
#   worker_extraction     UNTRUSTED (a candidate passage from a disposable worker)
#   validation_manifest   validator-owned (extraction confirmed against raw)
#   signed_evidence_record signer-owned (the only thing core trusts)
