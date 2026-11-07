# NEXUS — Hardcoding & Fake-Functionality Audit

Audit method: every backend file under `backend/app/`, every frontend file under `frontend/src/`, `demo_data/`, Docker/CI config, and `.env.example` was read line-by-line and cross-checked against the running API and the test suite. A targeted literal scan (magic numbers, inline JSON, static metrics) was performed on top.

## Verdict

**No hardcoded or fabricated operational data exists in any production code path.** No fake dashboard metrics, no fake activity feeds, no static agent statuses, no placeholder API responses, no hardcoded credentials, and no simulated progress. Every screen derives its state from the live backend, and every agent result is computed from the actually-ingested data.

The system is "fake-free" by construction, for three reasons:

1. **Deterministic domain logic** — stockout math (`business_service.stockout_risk`), supplier ranking (`compare_suppliers`), delay parsing (`communication_service.parse_delay_days`), and error classification (`incident_service`) are pure Python functions of the ingested events. There is no code path that returns a canned incident.
2. **Demo data is isolated and production-gated** — the only synthetic content is `demo_data/`, reachable solely through `POST /api/projects/{id}/demo`, which is disabled when `NEXUS_ENV=production` (`config.demo_enabled`). It is labeled "demo" in the UI and audit trail.
3. **The LLM is optional and sandboxed** — with no `OPENAI_API_KEY`, the app runs its rule-based engines and labels the method (`deterministic`/`rule_based`/`template`). The frontend renders the mode explicitly via the `Method` component.

## Backend audit (2.1) — results per checklist

| Concern | Result |
|---|---|
| Hardcoded API responses | None. All routes query the DB and serialize real rows. |
| Hardcoded dashboard statistics | None. `overview` aggregates `OperationalEvent`/`Incident`/`Recommendation`/`Task` counts. |
| Hardcoded agent outputs | None. Findings are `Finding` objects built from tool results + cited evidence. |
| Hardcoded inventory/supplier values | None in code. Values come from uploaded CSVs. |
| Hardcoded severity / risk score | Computed in `correlate.correlate` from documented rules. |
| Hardcoded user info / permissions | None. Read from DB per request. |
| Hardcoded credentials / API keys / DB config | None. All via `Settings` (env / `.env`). |
| Hardcoded timestamps / ownership / recovery status / execution results | None. Persisted + recomputed from events. |

## Frontend audit (2.2) — results per checklist

| Concern | Result |
|---|---|
| Static dashboard numbers | None. `CommandCenter` renders `overview.event_counts`, `pending_approvals`, `open_tasks`, `risk_score`. |
| Fake activity feeds / notifications | None exist. |
| Hardcoded agent statuses | None. `AgentWorkspace` polls `agent-runs` and renders real `AgentRun` rows (status, `tool_calls`, durations). |
| Fake progress bar | None. There is no progress bar; a pulsing "next step" marker shows only while `status === "running"` is true from the backend. |
| Placeholder API responses / fake charts | None. `IntelligenceGraph` renders real `hypotheses` from `/graph`. |
| Static approval states | None. `ResponseCenter` uses real `Recommendation` records. |
| Hardcoded report info | None. `ReportView` renders `/report` JSON. |

## Legitimate constants (kept intentionally)

These are correct and should not be removed:

- **Business-rule catalogs**: `policy_engine.ACTION_CATALOG` (action→risk/role/confidence), `incident_service._SIGNATURES` (error signatures), `communication_service` regexes and `_WORD_NUMBERS` (NLP rules), `business_service.classify_risk` thresholds.
- **Format specifications**: `normalizer` log/CSV/transcript schemas and regexes.
- **Enumerations**: `schemas.py` `Domain`/`Severity`/`Role`/`Method`.
- **Configuration defaults**: `config.py` `Settings` (all env-overridable).
- **UI presentation maps**: `ui.tsx` `DOMAIN`, `STATUS_LABEL`, `CHIP_TONES` (labels/colors only).
- **Cryptographic constants**: `audit.GENESIS = "0"*64` (hash-chain genesis).
- **Honest simulation label**: `approval_service.SIMULATED_NOTE` (tells the user a connector isn't live).
- **Test fixtures**: `tests/` and the `demo_data/` regression scenario (asserted against in tests only, never used by production paths).

## Fixes implemented this round

| Location | Problem | Fix | Verification |
|---|---|---|---|
| (none) | No hardcoded/fake data found | — | full read + grep + live API |
| `backend/app/rate_limit.py`, `api.py` | Auth endpoints had no brute-force throttle | Added sliding-window rate limiting on `/auth/login` and `/auth/register` | `test_rate_limiter_rejects_only_after_budget_is_used`, `test_login_is_rate_limited_outside_the_test_environment`, live check (ten 401 → 429) |
| `backend/app/main.py`, `api.py` | No request traceability | Added `X-Request-ID` correlation id + structured request log; request id recorded on `investigation.started` | `test_requests_carry_a_correlation_id`, `test_investigation_audit_records_the_request_id`, live check |
| `frontend/index.html` | Missing meta description / OG tags | Added description + Open Graph metadata | `npm run build` success |

## Remaining legitimate "hardcoded" items

None that are inappropriate. The only static, non-configurable numbers left are the business-rule thresholds documented above (e.g. `po_admin_threshold` default `5000`, `SUSPECT_DEPLOY_WINDOW = 30 min`), all of which are domain rules and — where operational — already environment-configurable via `Settings`.
