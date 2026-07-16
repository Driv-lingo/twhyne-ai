# Live-fetch v0 — controlled smoke test

**Status:** development-only, in-process retrieval prototype. NOT the isolated
Evidence Broker, NOT wired into answers, NOT for sensitive data. Enabling it
gives the Twhyne core outbound internet access. Run this on a non-sensitive
dev machine only.

## The 10-step controlled test

1. **Starts disabled.** Admin page → "Live evidence sources": the enable box
   is unchecked and the domain list empty on a fresh install.
2. **Admin-only to change.** With `TWHYNE_ADMIN_TOKEN` set, saving the policy
   requires the token (the admin page prompts for it). Confirm a non-admin
   `PUT /api/evidence/policy` is rejected.
3. **Add only** `visitdubai.com` (its `www.` is covered automatically), tick
   enable, Save.
4. **Fetch one fixed public page** with no personal data or query string:
   ```
   POST /api/evidence/fetch  {"url": "https://visitdubai.com/en"}
   ```
5. **Response carries the dev warning + an explicit outcome** (`FETCHED` or a
   distinct failure state). Confirm the `warning` field is present.
6. **Redirects individually checked** — if the page redirects, the final_url
   reflects the followed chain and any off-allowlist/private redirect returns
   `DESTINATION_REJECTED`.
7. **Recompute the stored-body hash** and match `decoded_hash`:
   ```
   sha256sum ~/.twhyne/rag/evidence_store/*.decoded.bin
   ```
   (prefix `sha256:` — it must equal the response's `decoded_hash`.)
8. **Audit is clean** — `~/.twhyne/rag/audit_ledger.jsonl` records the job id,
   domain and path only; NO query string and NO response body.
9. **Rejections work** — confirm each returns a rejection, not a fetch:
   - `https://evil.visitdubai.com/x` → `DESTINATION_REJECTED` (subdomain)
   - `https://10.0.0.1/x` → `DESTINATION_REJECTED` (private)
   - `http://visitdubai.com/x` → `DESTINATION_REJECTED` (not https)
10. **Disable immediately** after testing (untick, Save).

Record exactly what succeeded/failed.

## What this test does NOT prove (still open, do not claim)

- **Core internet isolation** — the fetch runs *inside* the core. Real
  isolation needs a separate service on a Docker `internal: true` network,
  proven unable to reach a public IP. Not built.
- **DNS-rebinding mitigation** — resolved addresses are filtered, but urllib
  re-resolves at connect time. Connect-time IP pinning (with SNI preserved)
  is not implemented.
- **Wire-level raw retention** — we store the exact *decoded* body (enough for
  a future validator), not the pre-decompression wire bytes.

Do not add extraction or planner behavior until the fetch runs outside the
core and connect-time address binding exists.
