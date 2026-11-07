# NEXUS — Known Issues

No **confirmed functional or security defects** were found; the existing test suite (57 passing) and a live end-to-end run both pass. The following are gaps and observations, not broken behavior.

## Reliability / scalability

- **[Low] In-process background work.** Investigations run via FastAPI `BackgroundTasks` in the API process (not a queue/worker). Restarts during a run are handled (`fail_interrupted_investigations`), but there is no horizontal fan-out. README lists Celery/Redis as roadmap — accurate.
- **[Info] `start.ps1` uses `python` (3.11 here) rather than `py -3.14`.** A first-run on a machine whose default Python is below 3.12 may build an out-of-support venv. The checked-in venv is already 3.14.3.

## Documentation inconsistencies

- **[Low] README lists "Icons: Lucide React"** but `frontend/package.json` has no `lucide-react` dependency and no source file imports it (verified by grep). Corrected in this audit.

## Security posture (see `SECURITY_AUDIT.md` for classification)

- ~~**[Low] No rate limiting / account lockout**~~ — **Resolved**: login/register are now rate-limited (`app/rate_limit.py`).
- **[Low] `/metrics` and `/healthz` are unauthenticated.** `/healthz` is intentional; `/metrics` exposes route/method/status/latency labels. Locally it binds to 127.0.0.1 and in Docker the backend is not published, so exposure is limited to the internal network.
- **[Info] Access token only** (no refresh token); 8-hour TTL, stateless logout.

## Testing gaps

- No frontend automated tests or ESLint config.
- No load/soak tests.
- No real-browser E2E in this environment (no browser-automation MCP).

## Not implemented (roadmap, by design)

- pgvector, Redis, Kafka, OpenTelemetry, real cloud connectors (AWS/K8s/Stripe/SAP), webhooks. Actions that would hit these are `simulated` and labeled as such.
