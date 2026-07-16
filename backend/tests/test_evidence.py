"""Phase 0A negative tests: the trust chain must FAIL closed on every attack
the roadmap names. Positive path is tested too, but the negatives are the
point - a compromised worker/validator/replay must not yield trusted evidence.
"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evidence.schema import (  # noqa: E402
    RetrievalJob, RawResponseRecord, WorkerExtraction,
    validate_extraction, sign_manifest, verify_evidence, finalization_check,
)

KEY = b"phase0a-test-signing-key"
PAGE = b"<html>The venue is temporarily closed for renovations.</html>"


def _job():
    return RetrievalJob(capability="travel_place_status",
                        query="Dubai Museum current operating status",
                        allowed_domains=["visitdubai.com"],
                        source_policy="official-travel-v1")


def _raw(job, url="https://visitdubai.com/museum", body=PAGE):
    return RawResponseRecord(job_id=job.job_id, final_url=url, status_code=200,
                             content_bytes=body, cert_fingerprint="cf:abc",
                             retrieved_at=time.time())


def _ext(job, passage="temporarily closed for renovations",
         assessment="contradicted"):
    return WorkerExtraction(job_id=job.job_id, claim="Dubai Museum is open",
                            assessment=assessment, cited_passage=passage,
                            claimed_hash="sha256:worker-says-whatever")


def test_happy_path_signs_and_verifies():
    job = _job(); raw = _raw(job); ext = _ext(job)
    m = validate_extraction(raw, ext, job)
    assert m["validation_result"] == "passed"
    assert m["status"] == "LIVE-SOURCE-CONTRADICTED"
    rec = sign_manifest(m, KEY)
    assert rec is not None
    ok, why = verify_evidence(rec, KEY, job.job_id, job.nonce,
                              acceptable_policies=["official-travel-v1"])
    assert ok, why


def test_worker_cannot_forge_passage():
    # A compromised worker cites text that isn't in the proxy-captured bytes.
    job = _job(); raw = _raw(job)
    ext = _ext(job, passage="The venue is OPEN and accepting visitors")
    m = validate_extraction(raw, ext, job)
    assert m["validation_result"] == "failed"
    assert "cited passage not found" in " ".join(m["reasons"])
    assert sign_manifest(m, KEY) is None  # signer refuses a failed manifest


def test_altered_bytes_change_hash():
    # The validator hashes the PROXY bytes, never the worker's claimed_hash.
    job = _job(); raw = _raw(job)
    m = validate_extraction(raw, _ext(job), job)
    assert m["raw_object_hash"] != "sha256:worker-says-whatever"


def test_domain_not_in_allowlist_fails():
    job = _job()
    raw = _raw(job, url="https://evil.example.com/museum")
    m = validate_extraction(raw, _ext(job), job)
    assert m["validation_result"] == "failed"
    assert "not in allowlist" in " ".join(m["reasons"])


def test_signer_rejects_arbitrary_input():
    assert sign_manifest({"anything": "goes"}, KEY) is None
    assert sign_manifest("not even a dict", KEY) is None
    # A manifest that claims passed but from an unauthorized validator version
    job = _job(); m = validate_extraction(_raw(job), _ext(job), job)
    m["validator_version"] = "attacker-validator-9.9"
    assert sign_manifest(m, KEY) is None


def test_tampered_signed_record_rejected():
    job = _job(); m = validate_extraction(_raw(job), _ext(job), job)
    rec = sign_manifest(m, KEY)
    rec["status"] = "OFFICIAL-SOURCE-SUPPORTED"  # flip the meaning
    ok, why = verify_evidence(rec, KEY, job.job_id, job.nonce)
    assert not ok and "signature mismatch" in why


def test_replay_of_another_jobs_evidence_rejected():
    job = _job(); m = validate_extraction(_raw(job), _ext(job), job)
    rec = sign_manifest(m, KEY)
    ok, why = verify_evidence(rec, KEY, "some-other-job", "some-other-nonce")
    assert not ok and "replay" in why


def test_expired_evidence_rejected():
    job = _job(); raw = _raw(job)
    m = validate_extraction(raw, _ext(job), job)
    rec = sign_manifest(m, KEY)
    future = raw.retrieved_at + job.max_age_hours * 3600 + 1
    ok, why = verify_evidence(rec, KEY, job.job_id, job.nonce, now=future)
    assert not ok and "expired" in why


def test_unacceptable_policy_rejected():
    job = _job(); m = validate_extraction(_raw(job), _ext(job), job)
    rec = sign_manifest(m, KEY)
    ok, why = verify_evidence(rec, KEY, job.job_id, job.nonce,
                              acceptable_policies=["some-stricter-policy"])
    assert not ok and "not acceptable" in why


def test_private_context_in_query_rejected():
    job = RetrievalJob(capability="travel_place_status",
                       query="Dubai status for my passport holder Levern",
                       allowed_domains=["visitdubai.com"],
                       source_policy="official-travel-v1")
    assert job.validate() is not None


def test_booking_claim_without_evidence_blocks_finalization():
    claims = [
        {"claim_id": "C1", "category": "opening_status", "evidence_id": "E1"},
        {"claim_id": "C2", "category": "price"},  # no evidence, no status
    ]
    r = finalization_check(claims)
    assert not r["finalization_allowed"]
    assert r["blocking_claims"] == ["C2"]


def test_booking_claim_with_explicit_unsupported_allows_finalization():
    claims = [
        {"claim_id": "C1", "category": "opening_status", "status": "UNVERIFIED"},
        {"claim_id": "C2", "category": "general"},  # not booking-sensitive
    ]
    assert finalization_check(claims)["finalization_allowed"]


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); passed += 1; print(f"PASS {fn.__name__}")
        except Exception:
            print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
