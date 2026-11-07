# NEXUS — API Reference

All routes are under `/api` and, except auth, require `Authorization: Bearer <token>`. Every lookup is tenant-scoped: another organization's id behaves exactly like a missing one (404). `NEXUS_ENV=production` disables the demo loader.

## Auth & users

| Method | Path | Access | Notes |
|---|---|---|---|
| POST | `/api/auth/register` | public | Creates tenant + admin. Rate-limited (5/min/IP). |
| POST | `/api/auth/login` | public | Returns JWT. Rate-limited (10/min per IP+email). |
| GET | `/api/me` | any user | Profile, org, `llm_enabled`, `demo_enabled`. |
| GET | `/api/users` | admin | Organization members. |
| POST | `/api/users` | admin | Provision a member with a role. |

## Projects & ingestion

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/api/projects` | any user | List org projects. |
| POST | `/api/projects` | analyst+ | Create a project. |
| POST | `/api/projects/{id}/uploads` | analyst+ | Multipart upload (supports `.csv, .tsv, .txt, .log, .json, .jsonl, .md`, up to configurable limit, default 25 MB). Returns per-file results incl. rejections. |
| GET | `/api/projects/{id}/files` | any user | List all uploaded datasets with metadata (size, type, status, event count). |
| GET | `/api/projects/{id}/files/{file_id}` | any user | Retrieve file details and sample parsed operational events. |
| DELETE | `/api/projects/{id}/files/{file_id}` | analyst+ | Delete an uploaded file and cascade-remove its ingested events/dependencies. |
| POST | `/api/projects/{id}/demo?stage=initial\|recovery` | analyst+ | Loads bundled demo data (disabled in production). |
| GET | `/api/projects/{id}/events?domain=&limit=` | any user | Normalized events. |
| GET | `/api/projects/{id}/overview` | any user | Counts, latest incident, pending approvals, open tasks, business risks. |

## Investigations & multi-agent graph

| Method | Path | Access | Notes |
|---|---|---|---|
| POST | `/api/projects/{id}/investigations` | analyst+ | 202; schedules the LangGraph investigation as a background task. |
| GET | `/api/incidents/{id}` | any user | Full incident state, findings, hypotheses, uncertainties, confidence. |
| GET | `/api/incidents/{id}/agent-runs` | any user | Per-agent status, tool calls, durations, findings. |
| GET | `/api/incidents/{id}/graph` | any user | Correlation nodes + edges. |
| GET | `/api/incidents/{id}/evidence` | any user | Cited source/calculation evidence. |
| GET | `/api/incidents/{id}/recommendations` | any user | Recommendations + policy verdicts + approval. |
| GET | `/api/incidents/{id}/report?format=json\|markdown` | any user | Executive report (markdown → download). |
| GET | `/api/incidents/{id}/tasks` | any user | Action tasks. |

## Response, governance & verification

| Method | Path | Access | Notes |
|---|---|---|---|
| POST | `/api/recommendations/{id}/decision` | approver+ | `{decision, comment, owner}`. One-time, policy re-checked, then recovery runs. |
| POST | `/api/incidents/{id}/verify` | analyst+ | Re-evaluates outcomes from post-action data. |
| PATCH | `/api/tasks/{id}` | analyst+ | `{status?, owner?}`. |
| GET | `/api/audit` | approver+ | Verified SHA-256 hash chain + entries. |

## System

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/healthz` | public | `{"status":"ok"}`. |
| GET | `/metrics` | public | Prometheus exposition. |

Every response carries an `X-Request-ID` header for tracing.
