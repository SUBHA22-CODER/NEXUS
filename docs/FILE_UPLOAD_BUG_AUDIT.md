# NEXUS File Upload & Document Ingestion Bug Audit

**Classification:** P0 Critical Defect  
**Target System:** NEXUS File Ingestion Pipeline & Multi-Agent Data Gateway  
**Date:** 2026-11-07  
**Author:** Full-Stack & Systems Engineering Team  

---

## Executive Summary

A comprehensive investigation into the NEXUS file upload and ingestion workflow revealed multiple interconnected root causes across the frontend presentation layer, backend validation, normalizer engines, database persistence, and reverse proxy infrastructure. 

Prior to this fix, users experienced file picker filtering issues, immediate rejections of valid operational data (e.g., TSV, JSON, general CSV, unstructured notes), an unconfigurable 5 MB upload ceiling, and lack of persistent file metadata.

---

## Root Cause Analysis (By Layer)

### 1. Frontend Layer (`frontend/src/screens/DataIngestion.tsx` & `src/api.ts`)

| Defect ID | Issue Description | Root Cause | Impact |
|:---|:---|:---|:---|
| **FE-01** | File dialog hides or grays out valid files | The `<input type="file" accept=".log,.jsonl,.csv,.txt,.md" />` attribute used non-standard extension-only filtering without MIME types or fallback. On Windows Explorer, unregistered extensions like `.log` or `.jsonl` cause the native file picker to filter out files or show an empty folder view. Additionally, `.tsv` and `.json` were missing. | Users could not see or click their files in the OS file picker. |
| **FE-02** | Instant auto-upload with no review or staging | The `<input onChange>` immediately called `send(e.target.files)` without staging the files into a user-inspectable queue. Users had no ability to verify file sizes, remove accidental selections, or see progress before dispatching. | Poor user control, accidental multi-file submissions, and zero pre-upload validation. |
| **FE-03** | Lack of persistent File Management UI | The UI only listed `Normalized events (latest 60)` from database rows. It did not display uploaded files, their processing statuses, file sizes, upload timestamps, or options to remove an ingested file. | Users had no confirmation of which files were successfully stored in their workspace. |
| **FE-04** | Hardcoded 5 MB messaging | UI text displayed `"Up to 5 MB each"` hardcoded, out of sync with any potential backend configuration changes. | Confusion when uploading larger datasets. |

---

### 2. Backend Normalizer Layer (`backend/app/services/normalizer.py`)

| Defect ID | Issue Description | Root Cause | Impact |
|:---|:---|:---|:---|
| **NORM-01** | Rigid CSV Schema Rejection | `_CSV_SCHEMAS` enforced an exact match against only four specific header subsets (`dependencies`, `inventory`, `suppliers`, `tasks`). Any general operational CSV (e.g. system metrics, transaction errors, customer orders, service incidents) triggered `UnsupportedFile("Unrecognised CSV columns")`. | Common operational CSV files were immediately rejected with "Not added". |
| **NORM-02** | Missing TSV & JSON Formats | `TEXT_SUFFIXES = (".log", ".txt", ".csv", ".jsonl", ".md")` completely excluded `.tsv` (Tab-Separated Values) and `.json` (JSON arrays / structured payload exports). | Uploading `.tsv` or `.json` raised `UnsupportedFile`. |
| **NORM-03** | TXT Fallback to Strict Regex Log Parser | In `normalize_file()`, any `.txt` file that did not match `looks_like_transcript()` (speaker lines like `Alice: ...`) fell back to `normalize_log()`. `normalize_log()` enforced a strict regex (`YYYY-MM-DD HH:MM:SS LEVEL service msg`). Unstructured operational notes, incident post-mortems, or bridge summaries failed every line and threw `"nothing could be read (Does not match the log format)"`. | Plaintext operational notes were 100% rejected. |
| **NORM-04** | Fragile Log Parser Rejection | In `normalize_log()`, if logs contained non-standard timestamps, multi-line stack traces, or free-form system messages, lines were added to `rejected`. If 0 lines matched, the file was rejected entirely rather than extracting partial telemetry. | Standard application logs failed ingestion. |

---

### 3. Backend Ingestion & Persistence Layer (`backend/app/services/ingestion.py` & `models.py`)

| Defect ID | Issue Description | Root Cause | Impact |
|:---|:---|:---|:---|
| **ING-01** | Hardcoded 5 MB Memory Limit | `config.py` defined `max_upload_bytes: int = 5 * 1024 * 1024`. Ingestion raised `IngestionError(f"{name} exceeds the 5 MB limit")`. | Valid datasets over 5 MB (e.g. large system logs or supply catalogs) were blocked. |
| **ING-02** | Missing `UploadedFile` Database Entity | Only `OperationalEvent` rows were persisted. There was no database entity to track uploaded files, original filenames, sizes, MIME types, processing outcomes, or creator attribution. | Inability to query, list, or delete specific uploaded files. |
| **ING-03** | Lack of File Deletion Endpoint | Deleting data was impossible without manual database truncation. Users could not remove a bad dataset or clean up an experiment. | Ingestion was irreversible. |

---

### 4. Infrastructure & Reverse Proxy Layer (`frontend/nginx.conf` & `.env.example`)

| Defect ID | Issue Description | Root Cause | Impact |
|:---|:---|:---|:---|
| **INF-01** | Nginx Reverse Proxy Body Size Limit | `frontend/nginx.conf` contained `client_max_body_size 6m;`. Even if backend limits were increased, containerized deployments through Nginx rejected payloads > 6 MB with HTTP 413. | Docker production deployments failed on uploads > 6 MB. |
| **INF-02** | Missing Environment Variable for Upload Limit | `.env.example` had no `MAX_UPLOAD_SIZE_MB` variable, preventing DevOps operators from tuning upload boundaries per environment. | Hardcoded limits required code modifications. |

---

## Remediation Roadmap

1. **Frontend File Picker & Staging Queue:**
   - Universal `accept` attribute covering `.csv, .tsv, .txt, .log, .json, .jsonl, .md`, standard MIME types, and `*/*` fallback.
   - Pre-upload file staging queue showing filename, size, format badge, and remove action before triggering upload.
   - Real-time upload progress / busy states.
   - Uploaded files table with status, size, events count, and delete capability.
2. **Configurable Limits (25 MB Default):**
   - Backend `Settings.max_upload_size_mb` configurable via `MAX_UPLOAD_SIZE_MB` or `NEXUS_MAX_UPLOAD_SIZE_MB` (default: 25 MB).
   - Nginx `client_max_body_size 50m;` in `frontend/nginx.conf`.
   - Dynamic synchronization: frontend fetches configured limit from `/api/me`.
3. **Expanded Normalizer Engine:**
   - Full TSV support (tab delimiter auto-detection).
   - Full JSON support (arrays of objects, log streams, nested data payloads).
   - Flexible CSV schema parser: maps arbitrary operational columns (`timestamp`, `service`, `severity`, `summary`, or general tabular attributes) into typed events.
   - Resilient TXT / Markdown parser: ingests free-form operational notes into the communication / operational domain without regex failure.
4. **Persistent File Tracking & Management:**
   - `UploadedFile` SQLAlchemy model tracking metadata, sizes, status, and event counts.
   - `GET /api/projects/{id}/files` to list files.
   - `DELETE /api/projects/{id}/files/{file_id}` to cleanly remove files and cascade delete corresponding events.
5. **Quality Verification:**
   - Comprehensive unit and integration test suite covering new formats, oversized file rejection, and file deletion.

