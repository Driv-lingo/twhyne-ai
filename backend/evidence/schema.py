"""Phase 0A: evidence object schemas + deterministic trust checks.

No network here. These functions encode the rules that let the TRUSTED side
certify evidence while treating the disposable worker as compromisable:

  - the validator recomputes the hash of the PROXY-captured bytes (never the
    worker's claimed hash) and confirms the worker's cited passage actually
    occurs in those bytes;
  - the signer accepts ONLY a validator-produced manifest (not arbitrary
    text/hashes), binding the signature to job id, nonce, policy, and hash;
  - the core rejects validly-signed evidence that is expired, replayed, or
    produced under an unacceptable policy.

Every check is fail-closed. See tests/test_evidence.py for the negative
cases (altered bytes, mismatched extraction, expiry, replay, unauthorized
signer, post-hoc claims).
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ---- status vocabulary (provenance, NOT truth) ---------------------------
# A live fetch proves who was contacted and what bytes arrived - never that
# the source is correct. "VERIFIED" is reserved for methods we actually have
# (math execution, tested code, signed-dataset match) and is NOT in this set.
STATUSES = (
    "LIVE-SOURCED",              # bytes obtained from an approved source now
    "OFFICIAL-SOURCE-SUPPORTED", # an official source's text supports the claim
    "LIVE-SOURCE-CONTRADICTED",  # an official source's text contradicts it
    "MULTI-SOURCE-CORROBORATED", # >=2 independent approved sources agree
    "SOURCE-CONFLICT",           # credible sources disagree
    "FETCH-FAILED",              # retrieval attempted, unsuccessful
    "UNVERIFIED",                # no current evidence obtained
)

# Booking-sensitive claim categories that MUST carry evidence or an explicit
# unsupported status before an answer can finalize.
BOOKING_SENSITIVE = (
    "opening_status", "price", "schedule", "availability", "legal_requirement",
)


SCHEMA_VERSION = "0b.1"


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


# ---- distinct outcome states (never collapse to UNVERIFIED) --------------
# Operators must be able to tell "forbidden" from "failed" from "contradicted".
OUTCOMES = (
    "POLICY_DENIED",            # the capability/policy forbade this request
    "DESTINATION_REJECTED",     # URL/DNS/redirect hit a blocked target
    "FETCH_FAILED",             # network attempt failed
    "CONTENT_LIMIT_EXCEEDED",   # response too large / decompression bomb
    "EXTRACTION_FAILED",        # worker produced nothing usable
    "VALIDATION_FAILED",        # extraction didn't match captured bytes
    "SIGNING_FAILED",           # signer refused
    "SOURCE_CONFLICT",          # credible official sources disagree
    "OFFICIAL_SOURCE_SUPPORTED",
    "LIVE_SOURCE_CONTRADICTED",
)


# ---- canonical serialization (freeze BEFORE any signing) -----------------
# Signatures must not depend on which runtime serialized the object. This is
# a deterministic canonical form: sorted keys, no insignificant whitespace,
# rejects duplicate keys and unknown fields, and always binds schema_version.
def canonical_bytes(obj: Dict[str, Any], allowed_fields) -> bytes:
    """Deterministic bytes for signing/verifying. Raises ValueError on
    duplicate keys, unknown fields, or a missing schema_version so nothing
    ambiguous ever enters the signed scope."""
    import json
    if not isinstance(obj, dict):
        raise ValueError("canonical_bytes requires a dict")
    if obj.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("schema_version missing or incompatible")
    unknown = set(obj) - set(allowed_fields)
    if unknown:
        raise ValueError(f"unknown fields in signed scope: {sorted(unknown)}")
    # json.dumps already rejects nothing for dup keys (Python dict can't hold
    # them), but a JSON string parsed with a dup-key hook would - so callers
    # that parse untrusted JSON must use _reject_dup_keys below.
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def parse_no_dup_keys(text: str) -> Dict[str, Any]:
    """Parse JSON, rejecting duplicate keys (which json.loads silently keeps
    the last of - an injection vector for signed payloads)."""
    import json

    def _hook(pairs):
        seen = set()
        for k, _ in pairs:
            if k in seen:
                raise ValueError(f"duplicate key {k!r}")
            seen.add(k)
        return dict(pairs)

    return json.loads(text, object_pairs_hook=_hook)


# ---- 1. retrieval_job (core -> broker; signed by core in 0B) -------------
@dataclass
class RetrievalJob:
    capability: str                     # e.g. "travel_place_status"
    query: str                          # generic PUBLIC terms only
    allowed_domains: List[str]
    source_policy: str                  # e.g. "official-travel-v1"
    max_age_hours: int = 24
    max_bytes: int = 5_000_000
    deadline_seconds: int = 30
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    nonce: str = field(default_factory=lambda: uuid.uuid4().hex)

    def validate(self) -> Optional[str]:
        if not self.capability or not self.query:
            return "capability and query are required"
        if not self.allowed_domains:
            return "allowed_domains must be non-empty (no open-web fetch)"
        # Public-terms guard (defense in depth; real PII scrubbing lives in
        # the broker). Reject obvious private context leaking into a query.
        low = self.query.lower()
        for bad in ("passport", "ssn", "medical", "my budget", "my calendar",
                    "credit card"):
            if bad in low:
                return f"query may carry private context ({bad!r})"
        return None


# ---- 2. raw_response_record (PROXY-owned, immutable) ---------------------
# The proxy - the retrieval boundary of record - captures what actually came
# back. The disposable worker never produces this; it only reads a copy.
@dataclass(frozen=True)
class RawResponseRecord:
    job_id: str
    final_url: str
    status_code: int
    transport_bytes: bytes              # EXACT bytes off the wire (maybe gzip)
    content_encoding: str               # e.g. "gzip", "identity"
    decoded_bytes: bytes                # bounded canonical decoded body
    cert_fingerprint: str
    retrieved_at: float

    @property
    def transport_hash(self) -> str:
        return _sha256(self.transport_bytes)

    @property
    def decoded_hash(self) -> str:
        # Extractor and validator compare passages against THIS canonical
        # decoded body - never against differently-decoded text, which could
        # let one component validate what another never saw.
        return _sha256(self.decoded_bytes)


# ---- 3. worker_extraction (UNTRUSTED) -----------------------------------
@dataclass
class WorkerExtraction:
    job_id: str
    claim: str
    assessment: str                     # supported | contradicted | unclear
    cited_passage: str                  # text the worker says is in the page
    claimed_hash: str                   # the worker's hash - NEVER trusted
    worker_image: str = "twhyne-fetcher-0.1.0"


# ---- 4. validation_manifest (VALIDATOR-owned) ---------------------------
def validate_extraction(raw: RawResponseRecord, ext: WorkerExtraction,
                        job: RetrievalJob) -> Dict[str, Any]:
    """The trusted validator reads the PROXY's bytes independently, recomputes
    the hash, and confirms the worker's cited passage occurs in those bytes.
    Returns a validation_manifest dict; result 'passed' only when every
    check holds. Never trusts the worker's claimed_hash.
    """
    reasons = []
    if raw.job_id != ext.job_id or raw.job_id != job.job_id:
        reasons.append("job_id mismatch across objects")
    true_hash = raw.decoded_hash
    # Domain of the final URL must be on the allowlist (post-redirect check).
    dom = raw.final_url.split("://", 1)[-1].split("/", 1)[0].lower()
    if not any(dom == d or dom.endswith("." + d) for d in job.allowed_domains):
        reasons.append(f"final domain {dom!r} not in allowlist")
    # The cited passage must occur in the canonical DECODED bytes (the same
    # representation the extractor was given).
    try:
        text = raw.decoded_bytes.decode("utf-8", errors="ignore")
    except Exception:
        text = ""
    if not ext.cited_passage or ext.cited_passage not in text:
        reasons.append("cited passage not found in captured bytes")
    if ext.assessment not in ("supported", "contradicted", "unclear"):
        reasons.append(f"invalid assessment {ext.assessment!r}")
    status = {"supported": "OFFICIAL_SOURCE_SUPPORTED",
              "contradicted": "LIVE_SOURCE_CONTRADICTED",
              "unclear": "UNVERIFIED"}.get(ext.assessment, "UNVERIFIED")
    manifest = {
        "manifest_id": "VM-" + uuid.uuid4().hex[:12],
        "job_id": job.job_id,
        "nonce": job.nonce,
        "decoded_content_hash": true_hash,
        "transport_hash": raw.transport_hash,
        "final_url": raw.final_url,
        "cert_fingerprint": raw.cert_fingerprint,
        "claim": ext.claim,
        "status": status if not reasons else "VALIDATION_FAILED",
        "cited_passage": ext.cited_passage if not reasons else "",
        "validator_policy": job.source_policy,
        "validator_version": "validator-0.1.0",
        "retrieved_at": raw.retrieved_at,
        "expires_at": raw.retrieved_at + job.max_age_hours * 3600,
        "validation_result": "passed" if not reasons else "failed",
        "reasons": reasons,
    }
    return manifest


# ---- 5. signed_evidence_record (SIGNER-owned) ---------------------------
# In production the key lives in the OS keystore / TPM / KMS and the signer is
# a separate process. Phase 0A models the POLICY: the signer accepts only a
# validator-produced manifest with result 'passed' and signs a bound subset -
# never arbitrary text or hashes.
_SIGNER_REQUIRED = ("manifest_id", "job_id", "nonce", "decoded_content_hash",
                    "validator_policy", "validation_result")

# The exact fields inside the signature. Frozen: unknown fields cannot enter
# the signed scope, and every field is always present (null if absent) so
# omitted-vs-null can't be confused.
_SIGNED_FIELDS = ("schema_version", "manifest_id", "job_id", "nonce",
                  "decoded_content_hash", "transport_hash", "final_url",
                  "claim", "status", "cited_passage", "policy",
                  "retrieved_at", "expires_at")


def sign_manifest(manifest: Dict[str, Any], signing_key: bytes,
                  authorized_validator_version: str = "validator-0.1.0"
                  ) -> Optional[Dict[str, Any]]:
    """Restricted signer. Returns a signed_evidence_record, or None if the
    manifest is not a passed manifest from the authorized validator. Signs a
    CANONICAL serialization bound to schema_version."""
    if not isinstance(manifest, dict):
        return None
    if any(k not in manifest for k in _SIGNER_REQUIRED):
        return None
    if manifest.get("validation_result") != "passed":
        return None
    if manifest.get("validator_version") != authorized_validator_version:
        return None
    payload = {
        "schema_version": SCHEMA_VERSION,
        "manifest_id": manifest["manifest_id"],
        "job_id": manifest["job_id"],
        "nonce": manifest["nonce"],
        "decoded_content_hash": manifest["decoded_content_hash"],
        "transport_hash": manifest.get("transport_hash"),
        "final_url": manifest.get("final_url"),
        "claim": manifest.get("claim"),
        "status": manifest.get("status"),
        "cited_passage": manifest.get("cited_passage"),
        "policy": manifest["validator_policy"],
        "retrieved_at": manifest.get("retrieved_at"),
        "expires_at": manifest.get("expires_at"),
    }
    body = canonical_bytes(payload, _SIGNED_FIELDS)
    sig = hmac.new(signing_key, body, hashlib.sha256).hexdigest()
    return {**payload, "signature": sig}


def verify_evidence(record: Dict[str, Any], signing_key: bytes,
                    job_id: str, nonce: str, now: Optional[float] = None,
                    acceptable_policies: Optional[List[str]] = None
                    ) -> tuple:
    """Core-side acceptance. Returns (ok, reason). Rejects tampering, replay
    (wrong job/nonce), expiry, and unacceptable policy - even for a validly
    signed record."""
    now = now if now is not None else time.time()
    if not isinstance(record, dict) or "signature" not in record:
        return False, "no signature"
    given = record["signature"]
    try:
        body = canonical_bytes({k: v for k, v in record.items()
                                if k != "signature"}, _SIGNED_FIELDS)
    except ValueError as e:
        return False, f"non-canonical record ({e})"
    expected = hmac.new(signing_key, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(given, expected):
        return False, "signature mismatch (tampered or forged)"
    if record.get("job_id") != job_id or record.get("nonce") != nonce:
        return False, "job/nonce mismatch (replay of another job's evidence)"
    if now > float(record.get("expires_at") or 0):
        return False, "evidence expired"
    if acceptable_policies is not None and \
            record.get("policy") not in acceptable_policies:
        return False, f"policy {record.get('policy')!r} not acceptable"
    return True, "ok"


# ---- claim-to-evidence binding (finalization gate) ----------------------
def finalization_check(answer_claims: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Every booking-sensitive claim must carry an evidence_id OR an explicit
    unsupported status, or finalization is blocked. `answer_claims` items:
    {claim_id, category, evidence_id?, status?}. This is the POST-generation
    pass; a pre-generation pass (not here) flags which claims to fetch for.
    """
    blocking = []
    for c in answer_claims:
        if c.get("category") in BOOKING_SENSITIVE:
            has_ev = bool(c.get("evidence_id"))
            explicit_unsupported = c.get("status") in (
                "UNVERIFIED", "FETCH-FAILED", "SOURCE-CONFLICT")
            if not (has_ev or explicit_unsupported):
                blocking.append(c.get("claim_id"))
    return {"finalization_allowed": not blocking,
            "blocking_claims": blocking}
