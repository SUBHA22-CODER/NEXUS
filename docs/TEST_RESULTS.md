# NEXUS — Test Results

All commands below were executed against the working tree; nothing is estimated.

## 1. Backend

| Command | Result | Exit code |
|---|---|---|
| `.venv/Scripts/python -m ruff check .` | `All checks passed!` | 0 |
| `.venv/Scripts/python -m pytest -q` | `61 passed, 13 warnings in ~6.5s` | 0 |

The 13 warnings are `DeprecationWarning` from `langsmith` (`asyncio.iscoroutinefunction` slated for removal in Python 3.16) — third-party, not application code. Skipped tests: **0**.

Four tests were added this round: a rate-limiter unit test, an auth-rate-limit 429 integration test, a correlation-id header test, and an audit request-id trace test.

## 2. Frontend

| Command | Result | Exit code |
|---|---|---|
| `npm run build` (`tsc --noEmit && vite build`) | success; 54 modules; `index.js` 320.57 kB (99.25 kB gzip), `index.css` 26.05 kB (5.77 kB gzip); built in 1.60 s | 0 |

No frontend test runner exists (see `TESTING_STRATEGY.md`).

## 3. Runtime health

- `GET /healthz` → `{"status":"ok"}`.
- `GET /metrics` → Prometheus exposition incl. `nexus_http_requests_total` and `nexus_http_request_seconds`.

## 4. Live end-to-end (fresh throwaway tenant, real API on 127.0.0.1:8000)

1. `POST /api/auth/register` → 201, `admin` role.
2. `POST /api/projects` → project id.
3. `POST /api/projects/{id}/demo` → 46 events ingested across 6 files.
4. `POST /api/projects/{id}/investigations` → 202, `running`.
5. Poll `GET /api/incidents/{id}` → `awaiting_approval`, severity `critical`, risk_score `87`, **10 findings**, **9 hypotheses**, uncertainties present.
   - Finding kinds: `commitment, decision, missing_owner, open_action, root_cause, service_impact, stockout_risk, supplier_delay`.
   - Cross-domain hypotheses: `communication→supply`, `infrastructure→execution`, `infrastructure→supply`.
6. `GET .../recommendations` → 6 recs: `service_rollback[proposed], assign_owner[proposed], expedite_supplier[proposed], notify_stakeholders[proposed], create_task[proposed], create_task[proposed]`.
7. `POST /api/recommendations/{rollback}/decision` (approved, owner set) → `executed`, connector `simulated`, verification `pending`.
8. `GET .../report` → title `Payment-service failure and SKU-1042 stockout risk`, status `in_recovery`, 6 recommendations, 22 evidence items.
9. `GET /api/audit` → `chain.valid = true`, 14 entries.
10. Cross-tenant read of the same incident by a second org → **HTTP 404** (isolation confirmed).

## 5. Failure-path tests (from the suite, all passing)

- Bad uploads refused with reasons (`.exe`, binary, empty, non-UTF-8, unrecognized CSV, noise).
- Failed agent is reported and the run continues (`incident` failed → `supply` still completed).
- Restart marks interrupted investigations `failed` and unblocks the project.
- Audit tampering is detected (`broken_at_sequence=2`).
- Recovery verification only trusts data ingested **after** execution; still-broken logs → `failed`.

## 7. This round's hardening verification (live, on a throwaway port)

- `X-Request-ID` present on every response (verified live: `4d7ed3d3…`).
- Login rate limiting: ten `401` then one `429` on the 11th attempt (verified live).
- `ruff check .` → `All checks passed!` (exit 0); `npm run build` → success (exit 0).

## 6. Not executed (environment limitations)

- Docker image builds: Docker Desktop engine was not running (`docker build` → daemon unreachable). `docker compose config` validated OK (exit 0); CI's `images` job covers builds.
- Real-browser DOM/console/network tests: no browser-automation MCP available in this session.
