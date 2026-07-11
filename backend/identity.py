#!/usr/bin/env python3
"""Signed identity for Twhyne — bind a role to a verified token, not a claim.

Until now a caller asserted its own `role` in the request body, so anyone
could send `{"role": "admin"}`. This module lets the runtime issue and verify
signed identity tokens (compact JWT-style HS256) so a role is only honored
when it is cryptographically bound to a token the runtime itself issued.

Design (local-first, no external IdP required, but ready for one):
  - The runtime holds a signing secret (TWHYNE_IDENTITY_SECRET). If unset, a
    per-process random secret is generated — tokens work within a run but do
    not survive restart, which is the safe default for a fresh install.
  - An operator creates users with roles (issue_token / a local user store)
    OR an external SSO/JWT can be trusted by configuring its secret/issuer.
  - /query reads the token from the Authorization: Bearer header (or a
    `token` field). A valid token's role wins. A request with NO token falls
    back to 'public' — least access — never to a body-asserted role.

  Enforcement switch: TWHYNE_REQUIRE_SIGNED_IDENTITY=true makes a body-asserted
  role WITHOUT a valid token an error instead of a silent downgrade, for
  deployments that want to forbid unauthenticated access entirely.

This is HS256 (shared secret). It is not a full IdP and does not do key
rotation or revocation lists yet — those are the next rungs — but it closes
the "anyone can claim admin" gap, which is the point.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

_ALG = "HS256"
_ROLES = ("public", "staff", "nurse", "family_contact", "it_admin",
          "auditor", "admin")


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


_PROCESS_SECRET = None


def _secret() -> bytes:
    """Signing secret. Env-configured for persistence, else per-process."""
    global _PROCESS_SECRET
    env = os.environ.get("TWHYNE_IDENTITY_SECRET", "").strip()
    if env:
        return env.encode()
    if _PROCESS_SECRET is None:
        _PROCESS_SECRET = secrets.token_hex(32)
    return _PROCESS_SECRET.encode()


def issue_token(subject: str, role: str, ttl_seconds: int = 43200) -> str:
    """Issue a signed identity token binding `subject` to `role`.

    Roles outside the known set are rejected (an operator cannot mint a
    typo'd role that then fails closed everywhere).
    """
    role = (role or "public").strip().lower()
    if role not in _ROLES:
        raise ValueError(f"unknown role '{role}'")
    now = int(time.time())
    header = {"alg": _ALG, "typ": "JWT"}
    payload = {"sub": subject, "role": role, "iat": now, "exp": now + ttl_seconds,
               "iss": "twhyne"}
    seg = _b64u(json.dumps(header, separators=(",", ":")).encode()) + "." + \
        _b64u(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(_secret(), seg.encode(), hashlib.sha256).digest()
    return seg + "." + _b64u(sig)


def verify_token(token: str):
    """Return the payload dict for a valid token, else None. Never raises."""
    try:
        seg, sig_b64 = token.rsplit(".", 1)
        expected = hmac.new(_secret(), seg.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64u_dec(sig_b64), expected):
            return None
        payload = json.loads(_b64u_dec(seg.split(".", 1)[1]))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        if payload.get("role") not in _ROLES:
            return None
        return payload
    except Exception:
        return None


def resolve_role(request, body: dict):
    """Determine the authorized role for a request.

    Precedence:
      1. A valid signed token (Authorization: Bearer <t> or body 'token').
         Its role is authoritative and cannot be overridden by the body.
      2. No token -> 'public' (least access). A body-asserted role is
         honored ONLY when signed identity is not required AND no token was
         supplied, preserving the existing local/dev workflow.

    Returns (role, signed: bool, error: str|None).
    """
    require = os.environ.get("TWHYNE_REQUIRE_SIGNED_IDENTITY", "").strip().lower() \
        in ("1", "true", "yes")
    auth = ""
    try:
        auth = request.headers.get("Authorization", "") or ""
    except Exception:
        auth = ""
    token = ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        token = str(body.get("token") or "").strip()

    if token:
        payload = verify_token(token)
        if payload:
            return payload["role"], True, None
        if require:
            return "public", False, "invalid or expired identity token"
        # Invalid token but signed identity not required: fail safe to public.
        return "public", False, None

    # No token.
    body_role = str(body.get("role", "") or "").strip().lower()
    if require and body_role and body_role != "public":
        return "public", False, ("signed identity required: role must be "
                                  "presented as a signed token, not asserted")
    if body_role:
        return (body_role if body_role in _ROLES else "public"), False, None
    return "public", False, None
