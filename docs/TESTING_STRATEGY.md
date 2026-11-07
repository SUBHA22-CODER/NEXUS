# NEXUS — Testing Strategy

## Current state

**Backend** — `pytest` (57 tests, all passing), `ruff` (clean). Two files:

- `tests/test_units.py` — pure-domain correctness: stockout math, supplier ranking, delay parser, transcript extraction (incl. LLM-injection rejection), CSV/log normalizers, root-cause heuristics, policy engine.
- `tests/test_platform.py` — HTTP/API + integration: the four-domain demo scenario, evidence tracing, approval-before-execution, RBAC, tenant isolation, idempotency, bad-upload rejection, prompt injection, closed-loop recovery, audit tamper detection, partial-data agent skipping, agent-failure containment, report export, restart recovery.

Test isolation: `conftest.py` pins `NEXUS_ENV=test`, in-memory SQLite (`sqlite://`), a fixed JWT secret, and no OpenAI key; a `fresh_db` autouse fixture recreates the schema per test. CI runs the same suite against SQLite **and** PostgreSQL 16.

**Frontend** — no automated tests. `npm run build` = `tsc --noEmit && vite build` (TypeScript strict + production bundle). No ESLint, no Vitest/Jest/Testing Library, no Playwright/Cypress.

**CI** (`.github/workflows/ci.yml`) — backend matrix (sqlite + postgres, `ruff check .` then `pytest -q` on Python 3.14), frontend (`npm ci` + `npm run build` on Node 24), and image builds for both Dockerfiles.

## Recommended strategy

Keep the existing layered approach and add the missing layers:

1. **Unit** (pure functions) — already strong; extend `test_units.py` as new calculators/parsers land.
2. **Service/API** (TestClient) — already strong; add coverage for the `overview` endpoint's `business_risks` aggregation and for `verify` on a rejected action.
3. **Frontend component tests** — add Vitest + React Testing Library for `ui.tsx`, `Login`, `ResponseCenter`, and the `useData` hook (loading/error/empty states).
4. **Frontend E2E** — Playwright against the running stack: login → create project → load demo → run investigation → approve → verify → export report; assert no console errors.
5. **Security regression** — keep the existing injection/tamper tests; add one for rate limiting once it is introduced.
6. **Performance** — a small load test (e.g. `k6`/`locust`) against `/projects/{id}/overview` and `/incidents/{id}` to pin latency budgets.

## Baseline commands (recorded results)

```bash
# backend/
.venv/Scripts/python -m ruff check .        # All checks passed! (exit 0)
.venv/Scripts/python -m pytest -q            # 57 passed, 13 warnings in 5.91s (exit 0)

# frontend/
npm run build                                 # tsc --noEmit && vite build — success (exit 0)
```

## Environment limitation (this audit)

No Chrome DevTools MCP / Playwright MCP is available in this session, so real-browser DOM/console/network testing could not be executed. The E2E evidence in this audit was produced through the live HTTP API (`TEST_RESULTS.md`). A browser-automation run should be added in an environment that provides it.
