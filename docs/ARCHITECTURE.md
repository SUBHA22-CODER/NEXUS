# NEXUS — Architecture

## Overview

NEXUS is a tenant-scoped, multi-agent operational intelligence platform. It ingests heterogeneous operational data (logs, CSVs, transcripts), normalizes it to a common event schema, runs four deterministic specialist agents under a LangGraph orchestrator, correlates findings across domains, generates policy-checked recommendations, and gates execution behind human approval with a hash-chained audit log and closed-loop verification.

## Components

### Backend (`backend/app`)

- **`main.py`** — FastAPI app; CORS; a middleware that assigns/generates an `X-Request-ID`, records Prometheus metrics, and logs one structured line per request; `/healthz` and `/metrics`.
- **`api.py`** — all REST routes (tenant-scoped via `_owned`); ingestion, investigations, decisions, verification, reports, audit.
- **`config.py`** — `Settings` (pydantic-settings, `NEXUS_` env prefix): DB URL, JWT secret/ttl, CORS, upload limits, PO threshold, OpenAI settings.
- **`db.py`** — SQLAlchemy engine (SQLite WAL / PostgreSQL pooling), `UTCDateTime`, `session_scope`, startup `fail_interrupted_investigations`.
- **`models.py`** — 12 tables: `tenants`, `users`, `projects`, `operational_events`, `incidents`, `dependencies`, `evidence`, `agent_runs`, `recommendations`, `approvals`, `tasks`, `audit_logs`.
- **`security.py`** — scrypt password hashing, HS256 JWT, `current_user` dependency, `require_role` RBAC.
- **`rate_limit.py`** — sliding-window limiter on login/register (disabled under `NEXUS_ENV=test`).
- **`schemas.py`** — shared Pydantic types (`NormalizedEvent`, `Finding`, `Hypothesis`, request/response models).
- **`orchestrator/`** — LangGraph state machines and agent nodes (`state.py`, `agents.py`, `correlate.py`, `graph.py`).
- **`services/`** — domain logic: `ingestion`, `normalizer`, `incident_service`, `business_service`, `communication_service`, `evidence_service`, `policy_engine`, `approval_service`, `audit`, `report_service`, `llm`.

### Frontend (`frontend/src`)

React 19 + TypeScript (strict) + Vite 7 + Tailwind 4. `App.tsx` hosts routing + session/project contexts; `api.ts` is a typed fetch client with a global 401 handler (token in `sessionStorage`); `ui.tsx` is the component kit; `screens/` holds the 11 pages.

## Data flow

1. **Ingest**: `POST /uploads` or `/demo` → `ingestion.ingest_bytes` → `normalizer` → `operational_events` (+ `dependencies`).
2. **Investigate**: `POST /investigations` creates an `Incident` and schedules `run_investigation` as a background task.
3. **Agents**: `triage` loads events/dependencies, marks unneeded agents `skipped`, then routes `incident → communication → supply → execution` (each persists an `AgentRun` with tool calls, findings, and evidence ids).
4. **Correlate**: `correlate.correlate` builds `Hypothesis` objects (observed vs inferred) and a rule-based `risk_score`; `plan` builds recommendations.
5. **Policy**: `policy_engine` assigns `risk_level`/`required_role`/allowed status; `finalize` persists state and sets `awaiting_approval` or `closed_no_action`.
6. **Decide → Execute → Verify**: `approval_service.decide` re-checks policy and role, records a one-time `Approval`, then the recovery graph (`execute → verify → update_status`) runs controlled (simulated or task-tracker) execution and re-evaluates outcomes from data ingested after the action.
7. **Report/Audit**: `/report` builds a JSON/Markdown report with evidence; `/audit` returns the verified hash chain.

## Isolation and correctness guarantees

- **Tenant isolation**: every row carries `tenant_id`; every lookup is scoped.
- **Determinism**: all numeric/risk math is pure Python; the LLM may reword facts but cannot add numbers (guarded by `only_known_numbers`).
- **Prompt-injection resistance**: transcript content is treated as untrusted data; extracted quotes/owners/numbers are re-validated against the source; action types come only from a fixed catalog.
- **Governance**: nothing executes before a human decision; single-decision enforcement; append-only, hash-chained audit with tamper detection.

## New in this round

- `rate_limit.py` + wiring (login/register throttling).
- `X-Request-ID` correlation id + structured HTTP logging, and the id is recorded on `investigation.started`.
- `index.html` meta description / Open Graph tags.

## Roadmap (not implemented, by design)

pgvector, Redis, Kafka, OpenTelemetry, real cloud connectors (AWS/K8s/Stripe/SAP), webhooks, durable background queue.
