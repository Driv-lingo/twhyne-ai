"""Destination validation (SSRF defense) — pure logic, frozen before sockets.

This is the check the GATEWAY runs at connect time and re-runs on EVERY
redirect (per OWASP SSRF guidance: allowlist, block private/loopback/
link-local/metadata, reject IP-literals, revalidate redirects). Kept as a
pure function so it is unit-testable without a network and reused identically
by the gateway implementation in 0B.

It does NOT resolve DNS here (that happens in the gateway, which must then
re-validate the RESOLVED address to defeat rebinding). This validates the URL
shape + host, and validate_resolved_ip validates an address the gateway
resolved.
"""

from __future__ import annotations

import ipaddress
import re
from typing import List, Optional, Tuple
from urllib.parse import urlsplit


# Cloud metadata + obvious internal hosts, blocked by name as defense in depth
# (the IP checks are the real guard).
_BLOCKED_HOSTNAMES = {
    "localhost", "metadata", "metadata.google.internal",
}
_METADATA_IPS = {"169.254.169.254", "fd00:ec2::254"}


def validate_url(url: str, allowed_domains: List[str]) -> Tuple[bool, str]:
    """Validate a URL before connecting. Returns (ok, reason|host).
    Fail-closed: HTTPS only, host on the allowlist, no IP-literal hosts,
    no userinfo, no non-standard ports."""
    try:
        parts = urlsplit(url)
    except Exception:
        return False, "unparseable URL"
    if parts.scheme != "https":
        return False, f"scheme {parts.scheme!r} not allowed (https only)"
    if "@" in (parts.netloc or ""):
        return False, "userinfo in URL not allowed"
    host = (parts.hostname or "").lower()
    if not host:
        return False, "no host"
    if parts.port not in (None, 443):
        return False, f"port {parts.port} not allowed"
    if host in _BLOCKED_HOSTNAMES:
        return False, f"blocked host {host!r}"
    # Reject IP-literal hosts outright - an approved fetch names a domain.
    if _is_ip_literal(host):
        return False, "IP-literal host not allowed (name a domain)"
    if not any(host == d or host.endswith("." + d) for d in allowed_domains):
        return False, f"host {host!r} not in allowlist"
    return True, host


def validate_resolved_ip(ip: str) -> Tuple[bool, str]:
    """Validate an address the gateway RESOLVED (call after DNS, before
    connect, to defeat rebinding). Blocks private/loopback/link-local/
    multicast/reserved/metadata ranges, IPv4 and IPv6."""
    if ip in _METADATA_IPS:
        return False, "cloud metadata address"
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False, f"unparseable IP {ip!r}"
    # Unwrap IPv4-mapped IPv6 (::ffff:169.254.169.254 etc.)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
        if str(addr) in _METADATA_IPS:
            return False, "cloud metadata address (v4-mapped)"
    if (addr.is_private or addr.is_loopback or addr.is_link_local
            or addr.is_multicast or addr.is_reserved or addr.is_unspecified):
        return False, f"non-public address {addr}"
    return True, str(addr)


def _is_ip_literal(host: str) -> bool:
    h = host.strip("[]")
    try:
        ipaddress.ip_address(h)
        return True
    except ValueError:
        pass
    # Decimal/octal/hex IPv4 tricks (e.g. 2130706433, 0x7f000001) - reject any
    # all-numeric or 0x-prefixed host that isn't a real domain.
    if re.fullmatch(r"0[xX][0-9a-fA-F]+", h) or re.fullmatch(r"\d+", h):
        return True
    return False


def validate_redirect(from_url: str, to_url: str,
                      allowed_domains: List[str]) -> Tuple[bool, str]:
    """Every redirect is revalidated with the SAME rules - a redirect from an
    approved page to a private address or off-allowlist domain is the classic
    SSRF/rebinding bypass."""
    return validate_url(to_url, allowed_domains)
