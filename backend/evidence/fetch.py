"""Live-fetch v0: DEVELOPMENT-ONLY IN-PROCESS retrieval prototype.

HONEST SCOPE (read before shipping this anywhere real):
  * The production fetch executes INSIDE the Twhyne core process/container.
    That means when it is enabled, the core has an outbound route and
    hostile network content enters the core process. This is NOT the
    isolated gateway/worker topology from the roadmap; it is an in-process
    prototype. "Twhyne does not access the internet" is false while this is
    enabled. Do not enable it for sensitive-data deployments, and do not
    wire it into the planner, until the fetch runs in a separately
    networked service (Phase 0B proper).
  * DNS rebinding is NOT fully mitigated. validate_resolved_ip runs on the
    address we resolve, but urllib re-resolves at connect time (a TOCTOU
    gap). Real mitigation requires connecting to the exact validated IP
    while preserving the original hostname for TLS SNI + cert check - not
    done here. Treated as defense-in-depth, not a guarantee.

The security-relevant logic (allowlist, redirect revalidation, private-IP
rejection, size/content limits, raw capture) is identical in CI and
production; only the TRANSPORT differs (real HTTPS vs test fixtures). The
fixture transport is a TEST-TIME argument only - the HTTP endpoint hardcodes
the production transport and never accepts a transport from a request.
"""
from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from .destination import validate_url, validate_resolved_ip
from .schema import RawResponseRecord

# A transport is: url -> dict(status:int, headers:dict[str,str] (lowercased),
#   body:bytes, resolved_ip:str|None, cert_fingerprint:str). It performs ONE
#   request and does NOT follow redirects - this module follows and
#   revalidates each hop itself (revalidation is the security boundary).
Transport = Callable[[str], Dict]

_REDIRECT_CODES = {301, 302, 303, 307, 308}
_OK_CONTENT = ("text/html", "text/plain", "application/json",
               "application/xhtml+xml")


def fetch_evidence(
    job_id: str,
    url: str,
    allowed_domains: List[str],
    transport: Transport,
    max_bytes: int = 5_000_000,
    max_redirects: int = 3,
    deadline_s: float = 30.0,
) -> Tuple[Optional[RawResponseRecord], str, str]:
    """Drive a bounded, allowlisted GET. Returns (record|None, outcome, detail).

    outcome is one of the schema OUTCOMES strings; a record is returned only
    on a clean 200 from an allowlisted, non-private destination.
    """
    start = time.time()
    current = url
    for _hop in range(max_redirects + 1):
        if time.time() - start > deadline_s:
            return None, "FETCH_FAILED", "deadline exceeded"
        ok, reason = validate_url(current, allowed_domains)
        if not ok:
            return None, "DESTINATION_REJECTED", reason
        try:
            resp = transport(current)
        except TimeoutError:
            return None, "FETCH_FAILED", "transport timeout"
        except Exception as e:
            return None, "FETCH_FAILED", f"transport error: {e}"
        # The address the transport actually connected to must be public
        # (defeats DNS rebinding: validated AFTER resolution, not just on URL).
        rip = resp.get("resolved_ip")
        if rip:
            ipok, ipreason = validate_resolved_ip(rip)
            if not ipok:
                return None, "DESTINATION_REJECTED", ipreason
        status = int(resp.get("status", 0))
        headers = {k.lower(): v for k, v in (resp.get("headers") or {}).items()}
        if status in _REDIRECT_CODES:
            loc = headers.get("location")
            if not loc:
                return None, "FETCH_FAILED", "redirect without location"
            current = urljoin(current, loc)  # revalidated at loop top
            continue
        if status != 200:
            return None, "FETCH_FAILED", f"status {status}"
        body = resp.get("body") or b""
        # size + declared-length guards (decompression bombs: cap the decoded
        # body too - transport is responsible for not handing us gigabytes).
        try:
            declared = int(headers.get("content-length", "0") or 0)
        except ValueError:
            declared = 0
        if declared > max_bytes or len(body) > max_bytes:
            return None, "CONTENT_LIMIT_EXCEEDED", f"body exceeds {max_bytes}"
        ctype = (headers.get("content-type") or "").split(";")[0].strip().lower()
        if ctype and not any(ctype == c for c in _OK_CONTENT):
            return None, "FETCH_FAILED", f"unsupported content-type {ctype!r}"
        raw = RawResponseRecord(
            job_id=job_id,
            final_url=current,
            status_code=200,
            transport_bytes=body,
            content_encoding=headers.get("content-encoding", "identity"),
            decoded_bytes=body,   # v0: transport hands us decoded bytes
            cert_fingerprint=resp.get("cert_fingerprint", ""),
            retrieved_at=time.time(),
        )
        return raw, "FETCHED", ""
    return None, "FETCH_FAILED", "too many redirects"


def production_transport(timeout_s: float = 15.0,
                         max_bytes: int = 5_000_000) -> Transport:
    """Real HTTPS transport (used only when live fetch is enabled by an
    operator). Resolves the host, rejects a non-public address BEFORE
    connecting, GET only, no cookies, bounded read. Imported lazily so the
    module has no hard network dependency for tests."""
    import socket
    import ssl
    import hashlib
    import urllib.request

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None  # surface 3xx to fetch_evidence instead of following

    def _transport(url: str) -> Dict:
        from urllib.parse import urlsplit
        host = urlsplit(url).hostname or ""
        # Resolve + validate every address the host maps to.
        try:
            infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        except Exception as e:
            raise RuntimeError(f"DNS resolution failed: {e}")
        # Validate EVERY resolved address (an attacker controlling DNS could
        # return one public + one private). NOTE: urllib re-resolves at
        # connect time, so this is defense-in-depth, NOT a rebinding
        # guarantee - see the module docstring. Real fix = connect to a
        # pinned validated IP with SNI preserved (Phase 0B proper).
        resolved = infos[0][4][0] if infos else ""
        for info in infos:
            ipok, ipreason = validate_resolved_ip(info[4][0])
            if not ipok:
                raise RuntimeError(f"resolved address rejected: {ipreason}")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "twhyne-fetch/0"})
        # Do NOT auto-follow redirects: we revalidate each hop ourselves.
        opener = urllib.request.build_opener(_NoRedirect())
        with opener.open(req, timeout=timeout_s) as r:
            body = r.read(max_bytes + 1)
            der = None
            try:
                der = r.fp.raw._sock.getpeercert(binary_form=True)  # best-effort
            except Exception:
                der = None
            cert_fp = ("sha256:" + hashlib.sha256(der).hexdigest()) if der else ""
            return {
                "status": r.status,
                "headers": dict(r.headers.items()),
                "body": body,
                "resolved_ip": resolved,
                "cert_fingerprint": cert_fp,
            }
    return _transport
