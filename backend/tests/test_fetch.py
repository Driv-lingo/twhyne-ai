"""Live-fetch v0 tests via the INJECTABLE transport - the full retrieval path
(allowlist, redirects, private-IP rejection, size/content limits, raw capture)
exercised with fixtures, no public internet. The user runs one manual smoke
test against a real approved domain; CI proves everything else."""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evidence.fetch import fetch_evidence  # noqa: E402

ALLOW = ["visitdubai.com"]
PAGE = b"<html><body>The venue is temporarily closed.</body></html>"


def _fixture(responses):
    """Build a transport from {url: response_dict}."""
    def _t(url):
        if url not in responses:
            raise RuntimeError(f"no fixture for {url}")
        return responses[url]
    return _t


def _resp(**kw):
    base = {"status": 200, "headers": {"content-type": "text/html"},
            "body": PAGE, "resolved_ip": "93.184.216.34",
            "cert_fingerprint": "sha256:cf"}
    base.update(kw)
    return base


def test_happy_path_returns_record():
    url = "https://visitdubai.com/museum"
    raw, outcome, _ = fetch_evidence("j1", url, ALLOW, _fixture({url: _resp()}))
    assert outcome == "FETCHED" and raw is not None
    assert raw.final_url == url and raw.transport_hash.startswith("sha256:")


def test_off_allowlist_rejected_before_transport():
    url = "https://evil.com/x"
    # transport would raise (no fixture); rejection must happen first
    raw, outcome, _ = fetch_evidence("j", url, ALLOW, _fixture({}))
    assert raw is None and outcome == "DESTINATION_REJECTED"


def test_redirect_to_private_ip_rejected():
    a = "https://visitdubai.com/a"
    resp = _resp(status=302, headers={"location": "https://10.0.0.1/b"})
    raw, outcome, _ = fetch_evidence("j", a, ALLOW, _fixture({a: resp}))
    assert raw is None and outcome == "DESTINATION_REJECTED"


def test_redirect_off_allowlist_rejected():
    a = "https://visitdubai.com/a"
    resp = _resp(status=302, headers={"location": "https://evil.com/b"})
    raw, outcome, _ = fetch_evidence("j", a, ALLOW, _fixture({a: resp}))
    assert raw is None and outcome == "DESTINATION_REJECTED"


def test_redirect_followed_when_allowlisted():
    a = "https://visitdubai.com/a"
    b = "https://visitdubai.com/b"
    fx = {a: _resp(status=301, headers={"location": b}), b: _resp()}
    raw, outcome, _ = fetch_evidence("j", a, ALLOW, _fixture(fx))
    assert outcome == "FETCHED" and raw.final_url == b


def test_resolved_private_ip_rejected():
    url = "https://visitdubai.com/x"
    resp = _resp(resolved_ip="127.0.0.1")   # DNS-rebinding shape
    raw, outcome, _ = fetch_evidence("j", url, ALLOW, _fixture({url: resp}))
    assert raw is None and outcome == "DESTINATION_REJECTED"


def test_oversized_body_rejected():
    url = "https://visitdubai.com/big"
    resp = _resp(body=b"x" * 20, headers={"content-type": "text/html",
                                          "content-length": "999999999"})
    raw, outcome, _ = fetch_evidence("j", url, ALLOW, _fixture({url: resp}),
                                     max_bytes=1000)
    assert raw is None and outcome == "CONTENT_LIMIT_EXCEEDED"


def test_unsupported_content_type_rejected():
    url = "https://visitdubai.com/pdf"
    resp = _resp(headers={"content-type": "application/pdf"})
    raw, outcome, _ = fetch_evidence("j", url, ALLOW, _fixture({url: resp}))
    assert raw is None and outcome == "FETCH_FAILED"


def test_non_200_is_fetch_failed():
    url = "https://visitdubai.com/404"
    raw, outcome, _ = fetch_evidence("j", url, ALLOW,
                                     _fixture({url: _resp(status=404)}))
    assert raw is None and outcome == "FETCH_FAILED"


def test_http_scheme_rejected():
    url = "http://visitdubai.com/x"
    raw, outcome, _ = fetch_evidence("j", url, ALLOW, _fixture({}))
    assert raw is None and outcome == "DESTINATION_REJECTED"


def test_transport_timeout_is_fetch_failed():
    url = "https://visitdubai.com/slow"

    def _t(u):
        raise TimeoutError("slow")
    raw, outcome, _ = fetch_evidence("j", url, ALLOW, _t)
    assert raw is None and outcome == "FETCH_FAILED"


def test_redirect_loop_bounded():
    a = "https://visitdubai.com/a"
    fx = {a: _resp(status=302, headers={"location": a})}
    raw, outcome, _ = fetch_evidence("j", a, ALLOW, _fixture(fx),
                                     max_redirects=2)
    assert raw is None and outcome == "FETCH_FAILED"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); passed += 1; print(f"PASS {fn.__name__}")
        except Exception:
            print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
