# NEXUS — Project Audit

Audit performed: 2026-11-07 (Asia/Calcutta). All claims below are backed by actual inspection or execution; nothing is inferred from the README alone.

## 1. What was inspected

| Area | Files | Method |
|---|---|---|
| Repository layout | full tree (git-tracked files) | directory walk |
| Backend entry points | `backend/app/main.py`, `api.py` | read |
| Configuration | `config.py`, `pyproject.toml`, `requirements*.txt`, `.env.example`, `docker-compose.yml` | read |
| Data layer | `db.py`, `models.py` (12 tables) | read |
| Auth/RBAC | `security.py`, `schemas.py` | read |
| API surface | `api.py` (all routes) | read |
| Orchestration | `orchestrator/state.py`, `agents.py`, `correlate.py`, `graph.py` | read |
| Domain services | `services/*` (11 modules) | read |
| Frontend | `src/App.tsx`, `api.ts`, `main.tsx`, `ui.tsx`, `screens/*`, `vite.config.ts`, `tsconfig.json` | read |
| Tests | `tests/conftest.py`, `test_units.py`, `test_platform.py` | read |
| CI/CD | `.github/workflows/ci.yml`, Dockerfiles, `nginx.conf`, `start.ps1` | read |
| Data | `demo_data/*` | referenced by tests |

## 2. Existing architecture

- **Backend**: FastAPI 0.162 (ASGI via uvicorn 0.54), SQLAlchemy 2.1 ORM, Pydantic v2. SQLite for local runs and PostgreSQL (`psycopg` 3.3) in CI/Docker, unified behind `NEXUS_DATABASE_URL`.
- **Frontend**: React 19 + TypeScript 5.6 (strict) + Vite 7 + Tailwind CSS 4. Token kept in `sessionStorage`; typed fetch client with a global 401 handler.
- **Orchestration**: two decoupled LangGraph 1.2 state machines — `investigation` (triage → 4 agents → correlate → plan → policy → finalize) and `recovery` (execute → verify → status). Agents never call each other; a router picks the next node. State is persisted on the `Incident` row between the two graphs, so recovery can run hours later.
- **Four agents** (deterministic tools, structured findings): Infrastructure (`log_correlator`), Communication (`transcript_extractor`), Supply (`stockout_calculator`, `supplier_comparison`), Execution (`ownership_checker`).
- **Governance**: deterministic policy engine (`ACTION_CATALOG`) + SHA-256 hash-chained, append-only audit log + RBAC (`viewer`/`analyst`/`approver`/`admin`) + human-in-the-loop decisions.
- **LLM**: optional OpenAI (`gpt-4o-mini`); every LLM output is schema-validated and re-checked against the source, and numbers are computed deterministically (never by the model). Without a key the whole system runs rule-based.

## 3. Working features (verified)

- Full lifecycle: register → project → upload/demo ingest → investigation → findings/hypotheses → recommendations → human decision → simulated execution → closed-loop verification → report export → audit chain. Confirmed live against the running API (46 events ingested, `awaiting_approval`, risk 87, 10 findings, 9 hypotheses, 6 recommendations, 22 evidence items, audit chain valid/14 entries).
- Deterministic stockout math, supplier ranking, delay parsing, transcript extraction (all unit-tested).
- Tenant isolation (cross-tenant reads return 404), RBAC role escalation, prompt-injection resistance, audit tamper detection, idempotent re-upload, safe file-upload validation.
- Metrics (`/metrics`) and health (`/healthz`).

## 4. Broken features

None found. No confirmed defects requiring code changes (see `BUG_FIX_LOG.md`).

## 5. Missing features (relative to the stated target stack)

These are **roadmap items**, not defects. Confirmed **not** implemented:

- **pgvector** — not in `requirements.txt`; no vector columns. (Prompt's "vector search: pgvector" is absent.)
- **Redis** — not used; background work runs in-process (`BackgroundTasks`).
- **Kafka** — not implemented (README lists it under "Roadmap").
- **OpenTelemetry** — not implemented; only `prometheus-client` is present.
- **Real external connectors** (AWS ECS/K8s/Stripe/SAP) — actions are `simulated` by design and clearly labeled (`SIMULATED_NOTE`).
- **Refresh tokens / sessions** — access-token-only JWT (480-minute TTL default).
- **Frontend automated tests** — no Vitest/Jest/Testing Library; no ESLint config. Build is `tsc --noEmit && vite build`.

## 6. Security risks

See `SECURITY_AUDIT.md`. Summary: no Critical/High findings; a small number of Low/Informational items (no rate limiting on auth, unauthenticated `/metrics`/`/healthz`, global email uniqueness).

## 7. Testing gaps

See `TESTING_STRATEGY.md`. Backend coverage is strong (57 tests). Gaps: no frontend unit/component/E2E tests, no real-browser tests in this environment (no Chrome DevTools MCP), no load/soak tests.

## 8. Deployment risks

- Docker Compose file is valid (`docker compose config` → exit 0); images are built by CI, not verified locally (Docker Desktop engine was not running during this audit).
- `start.ps1` invokes `python` (3.11 on this machine) while the project targets Python 3.12+/3.14; a first-run on a machine whose default `python` is <3.12 may create an out-of-support venv. The committed venv is 3.14.3.
- Investigation runs as an in-process background task, not a durable queue; a process restart mid-investigation marks it `failed` (handled deliberately by `fail_interrupted_investigations`).
