# NEXUS — Security Audit

Scope: source review of all backend/frontend files, `demo_data`, Docker/CI config; live verification against the running API; secret scan (grep for key patterns) and git-tracked-file check. No destructive or production-changing actions were performed.

## Classification of findings

| Severity | Count | Remediated |
|---|---|---|
| Critical | 0 | — |
| High | 0 | — |
| Medium | 0 | 1 (rate limiting added) |
| Low | 3 | No |
| Informational | 4 | 1 (README) |

## Findings

### MED-1 — Rate limiting on auth endpoints — RESOLVED
`POST /api/auth/login` (10/min per IP+email) and `/api/auth/register` (5/min per IP) now throttle via `app/rate_limit.py` with a `Retry-After` header. Verified by `test_login_is_rate_limited_outside_the_test_environment` and a live check (ten 401 → one 429). Note: the limiter is in-process; a multi-worker deployment should still add a shared gateway/Redis limiter.

### LOW-1 — `/metrics` and `/healthz` are unauthenticated
`/healthz` is intentionally public. `/metrics` (Prometheus) is unauthenticated and exposes request/latency by route. Exposure is limited: uvicorn binds 127.0.0.1 locally and the backend is unpublished in `docker-compose.yml`. **Recommendation:** put `/metrics` behind auth or a scrape-only network path.

### LOW-2 — Global email uniqueness across tenants
`User.email` has a single `unique` index, so the same address cannot exist in two organizations. Not a security hole, but a multi-tenant product constraint worth confirming. (Login uses a generic error, so this does not enable enumeration.)

### LOW-3 — `start.ps1` selects an out-of-support Python
See `KNOWN_ISSUES.md`. Not a runtime vulnerability, but a supply-chain/footgun for first-run installs.

### INFO-1 — Access token only, no refresh token (resolved as intended design)
JWT is HS256 with `sub`/`tid`/`iat`/`exp`; 480-minute TTL; no refresh/rotation. Stateless logout is a documented tradeoff.

### INFO-2 — `metrics_middleware` labels unmatched paths as `unmatched`
Cosmetic only; `/healthz` and `/metrics` are labeled correctly (verified). No action.

### INFO-3 — README "Icons: Lucide React" is inaccurate
Verified no `lucide-react` dependency or imports. **Corrected** in README (only change made to the repo).

### INFO-4 — Append-only audit enforced at ORM layer
`audit_logs` blocks UPDATE/DELETE via SQLAlchemy `before_update`/`before_delete` events. Raw SQL could bypass this (as the tamper test itself demonstrates by updating via `text()`), but tampering is then **detected** by `verify_chain`. This matches the intended tamper-evident (not tamper-proof) design.

## Verified-safe areas (evidence)

- **Password hashing:** `scrypt` (n=2^14, r=8, p=1) with 16-byte random salt; constant-time compare.
- **JWT:** HS256, `exp` enforced by `pyjwt` decode; role re-read from DB every request.
- **RBAC:** `viewer`/`analyst`/`approver`/`admin` rank; `require_role` on write/approve routes. Tests prove viewer/analyst/approver cannot approve a rollback; approver cannot exceed the PO threshold.
- **Tenant isolation:** every lookup is tenant-scoped (`_owned`); cross-tenant reads return 404 (verified live: HTTP 404).
- **Input security:** uploads bounded to 5 MB / 50k lines, binary/UTF-8/size validated, filenames basename-stripped, content deduplicated; no file is written to disk.
- **SQL injection:** SQLAlchemy ORM/parameterized queries throughout (no string-built SQL except the test-only tamper statement).
- **Prompt injection:** transcripts are treated as untrusted data; the LLM is instructed to ignore instructions in them; extracted quotes/numbers/owners are re-validated against the source; action types come only from a fixed catalog; policy re-checks every approval. Covered by `test_transcript_injection_cannot_create_or_approve_actions` and `test_llm_extraction_cannot_invent_quotes_numbers_or_owners`.
- **Secrets:** no hardcoded credentials/keys; `.env` gitignored and untracked; `nexus.db` gitignored. Secret scan returned zero matches.
- **Governance:** nothing executes before an approved human decision; approval is idempotent (single decision enforced at DB + service level); duplicate execution prevented via `UPDATE ... WHERE status='proposed'`.
