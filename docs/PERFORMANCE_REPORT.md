# NEXUS — Performance Report

Measure-first; only observed numbers are reported. Environment: local Windows host, API on 127.0.0.1:8000, deterministic (no OpenAI key) path.

## Backend

| Measurement | Value | Method |
|---|---|---|
| `/healthz` latency | min 11 ms, **p50 14 ms**, p95 16 ms, max 186 ms | 20 sequential requests, Stopwatch |
| Full investigation (46 events, 4 agents + correlate + plan + policy + finalize) | **198 ms** | Stopwatch around `POST /investigations` → status ≠ running |
| Test suite | 57 tests in 5.91 s | `pytest -q` |

Observations:
- No blocking calls inside `async` routes (all routes are `def`, run in threadpool; the heavy graph is invoked as a `BackgroundTask`).
- DB session hygiene is clean (`session_scope` context manager, `expire_on_commit=False`, SQLite WAL + `foreign_keys=ON`, Postgres `pool_pre_ping=True`, pool_size 10 / overflow 20).
- Queries are indexed on the hot paths (`project_id`, `tenant_id`, `incident_id`, `(project_id, domain, occurred_at)`); no N+1 found in review.

## Frontend

| Measurement | Value |
|---|---|
| Production JS bundle | 320.57 kB (99.25 kB gzip) |
| Production CSS | 26.05 kB (5.77 kB gzip) |
| Build time | 1.60 s (tsc + Vite) |
| Modules | 54 |

The bundle is React 19 + React Router + app code with no heavy charting library (the graph is rendered with custom SVG). Reasonable for the feature set; the main future lever is route-level code-splitting of the report/graph views.

## AI layer

- No OpenAI key set → LLM path is entirely skipped (`llm.available()` false); deterministic rule engines run instead.
- When enabled: `temperature=0`, `max_retries=1`, 30 s timeout, and a single structured call each for transcript extraction and narrative (bounded). Numbers are guarded by `only_known_numbers`, so a model cannot inject a fabricated figure.

## Recommendations (only if load demands it — not for appearance)

- Move investigations to a durable queue (Celery/Redis) only when multi-worker horizontal scaling is actually required.
- Add `/metrics`-based alerting (latency histogram already exists) and a small load test before launch.
- Route-level lazy loading for the frontend if the bundle grows.
