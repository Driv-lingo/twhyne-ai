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
    canonical_bytes, parse_no_dup_keys, SCHEMA_VERSION, _SIGNED_FIELDS,
)
from evidence.destination import (  # noqa: E402
    validate_url, validate_resolved_ip, validate_redirect,
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
                             transport_bytes=body, content_encoding="identity",
                             decoded_bytes=body, cert_fingerprint="cf:abc",
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
    assert m["status"] == "LIVE_SOURCE_CONTRADICTED"
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
    assert m["decoded_content_hash"] != "sha256:worker-says-whatever"


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


# ---- freeze-first: destination validation (SSRF) -------------------------
def test_https_only_and_allowlist():
    ok, _ = validate_url("https://visitdubai.com/x", ["visitdubai.com"])
    assert ok
    assert validate_url("https://www.visitdubai.com/x", ["visitdubai.com"])[0]
    assert not validate_url("http://visitdubai.com/x", ["visitdubai.com"])[0]
    assert not validate_url("https://evil.com/x", ["visitdubai.com"])[0]
    # arbitrary subdomains and suffix tricks are NOT allowed (exact host + www)
    assert not validate_url("https://evil.visitdubai.com/x", ["visitdubai.com"])[0]
    assert not validate_url("https://visitdubai.com.attacker.example/x",
                            ["visitdubai.com"])[0]


def test_ip_literal_and_userinfo_and_port_rejected():
    dom = ["visitdubai.com"]
    assert not validate_url("https://169.254.169.254/", dom)[0]
    assert not validate_url("https://2130706433/", dom)[0]        # decimal IP
    assert not validate_url("https://0x7f000001/", dom)[0]        # hex IP
    assert not validate_url("https://user@visitdubai.com/", dom)[0]
    assert not validate_url("https://visitdubai.com:8443/", dom)[0]


def test_resolved_ip_blocks_private_and_metadata():
    assert not validate_resolved_ip("127.0.0.1")[0]
    assert not validate_resolved_ip("10.0.0.5")[0]
    assert not validate_resolved_ip("169.254.169.254")[0]         # metadata
    assert not validate_resolved_ip("::1")[0]
    assert not validate_resolved_ip("::ffff:169.254.169.254")[0]  # v4-mapped
    assert validate_resolved_ip("93.184.216.34")[0]               # public


def test_redirect_to_private_or_offlist_rejected():
    dom = ["visitdubai.com"]
    assert not validate_redirect("https://visitdubai.com/a",
                                 "https://10.0.0.1/b", dom)[0]
    assert not validate_redirect("https://visitdubai.com/a",
                                 "https://evil.com/b", dom)[0]


# ---- freeze-first: canonical serialization -------------------------------
def test_canonical_is_order_independent():
    a = {"schema_version": SCHEMA_VERSION, "job_id": "1", "nonce": "2"}
    b = {"nonce": "2", "job_id": "1", "schema_version": SCHEMA_VERSION}
    fields = ("schema_version", "job_id", "nonce")
    assert canonical_bytes(a, fields) == canonical_bytes(b, fields)


def test_canonical_rejects_unknown_field_and_bad_version():
    fields = ("schema_version", "job_id")
    try:
        canonical_bytes({"schema_version": SCHEMA_VERSION, "job_id": "1",
                         "sneaky": "x"}, fields)
        assert False, "unknown field should raise"
    except ValueError:
        pass
    try:
        canonical_bytes({"schema_version": "999", "job_id": "1"}, fields)
        assert False, "bad schema_version should raise"
    except ValueError:
        pass


def test_parse_rejects_duplicate_keys():
    try:
        parse_no_dup_keys('{"a": 1, "a": 2}')
        assert False, "dup key should raise"
    except ValueError:
        pass
    assert parse_no_dup_keys('{"a": 1, "b": 2}') == {"a": 1, "b": 2}


def test_signed_record_is_canonical_and_binds_schema_version():
    job = _job(); m = validate_extraction(_raw(job), _ext(job), job)
    rec = sign_manifest(m, KEY)
    assert rec["schema_version"] == SCHEMA_VERSION
    assert set(rec) - {"signature"} == set(_SIGNED_FIELDS)


def test_transport_and_decoded_hashes_distinct_when_encoded():
    import gzip
    job = _job()
    decoded = b"The venue is temporarily closed for renovations."
    transport = gzip.compress(decoded)
    raw = RawResponseRecord(job_id=job.job_id, final_url="https://visitdubai.com/m",
                            status_code=200, transport_bytes=transport,
                            content_encoding="gzip", decoded_bytes=decoded,
                            cert_fingerprint="cf", retrieved_at=time.time())
    assert raw.transport_hash != raw.decoded_hash
    ext = WorkerExtraction(job_id=job.job_id, claim="open",
                           assessment="contradicted",
                           cited_passage="temporarily closed",
                           claimed_hash="x")
    m = validate_extraction(raw, ext, job)
    assert m["validation_result"] == "passed"  # matched against DECODED


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
