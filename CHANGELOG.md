# Changelog

All notable changes to NEXUS are documented here. The project follows [Conventional Commits](https://www.conventionalcommits.org/) and [Semantic Versioning](https://semver.org/).

## [0.1.1] - 2026-11-07

### Security
- Added sliding-window rate limiting on `/api/auth/login` (10/min per IP+email) and `/api/auth/register` (5/min per IP), with a `Retry-After` header. Disabled under `NEXUS_ENV=test`.

### Observability
- Added request correlation IDs: every response carries an `X-Request-ID` header (honoring an inbound one), a structured request log line, and the id is recorded on the `investigation.started` audit entry for end-to-end traceability.

### Frontend
- Added `meta description` and Open Graph tags to `index.html`.

### Docs
- Added `docs/HARDCODING_AUDIT.md`, `docs/AGENT_EVALUATION.md`, `docs/UI_UX_AUDIT.md`, `docs/UI_UX_IMPLEMENTATION_REPORT.md`, `docs/ARCHITECTURE.md`, `docs/API.md`.
- Updated `docs/SECURITY_AUDIT.md`, `docs/TEST_RESULTS.md`, `docs/KNOWN_ISSUES.md`, `docs/PRODUCTION_READINESS.md`.

### Tests
- Added 4 tests (61 total): rate-limiter unit test, login 429 integration test, correlation-id header, and request-id audit trace.

## [0.1.0] - initial release

- Four-domain multi-agent investigation (infrastructure, communication, supply, execution) on LangGraph.
- Deterministic stockout/supplier/delay/error-classification engines with optional sandboxed OpenAI fallback.
- Cross-domain correlation, evidence-backed findings, policy engine, human-in-the-loop approvals.
- SHA-256 hash-chained, append-only audit log with closed-loop recovery verification.
- React 19 + TypeScript frontend with per-domain intelligence graph.
