# NEXUS

**Autonomous Cross-Domain Risk Intelligence & Response Platform**

> *One Intelligence Layer. Multiple Operational Domains. Coordinated Decisions.*

[![CI](https://github.com/SUBHA22-CODER/NEXUS/actions/workflows/ci.yml/badge.svg)](https://github.com/SUBHA22-CODER/NEXUS/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange.svg)](https://github.com/langchain-ai/langgraph)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.8-blue.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-7-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [The Problem: The Local Optimization Trap](#the-problem-the-local-optimization-trap)
3. [Our Solution](#our-solution)
4. [Key Features](#key-features)
5. [System Architecture](#system-architecture)
6. [Multi-Agent Architecture](#multi-agent-architecture)
7. [Technology Stack](#technology-stack)
8. [Project Structure](#project-structure)
9. [Getting Started](#getting-started)
10. [Environment Variables](#environment-variables)
11. [The Demo Scenario Walkthrough](#the-demo-scenario-walkthrough)
12. [API Reference](#api-reference)
13. [Testing & Quality Verification](#testing--quality-verification)
14. [Security & Governance](#security--governance)
15. [Contributing & License](#contributing--license)

---

## Project Overview

**NEXUS** is an autonomous operational risk intelligence and governed response platform. Modern enterprise organizations operate complex, interdependent ecosystems where software infrastructure, global supply chains, financial transactions, and cross-functional teams interact continuously. 

When incidents occur, operational data is fragmented across isolated monitoring dashboards, enterprise resource planning (ERP) databases, and ad-hoc communication transcripts. Teams resolve issues in isolation, unaware that fixing an infrastructure failure can instantly trigger a downstream supply chain stockout or financial breach.

NEXUS ingests raw system logs, inventory metrics, supplier catalogs, architecture dependency graphs, task trackers, and meeting transcripts into a unified operational canvas. Using decoupled **LangGraph** multi-agent state machines, deterministic risk calculators, and policy-governed approval gates, NEXUS:
- Correlates cross-domain failure ripples that siloed tools cannot detect.
- Synthesizes prioritized, evidence-backed recovery plans.
- Enforces strict human-in-the-loop governance before any action is executed.
- Records all actions in a cryptographically verifiable SHA-256 audit chain.
- Automatically verifies actual recovery outcomes against post-incident telemetry.

---

## The Problem: The Local Optimization Trap

During major incidents, modern operations suffer from **siloed domain visibility**:

```
┌─────────────────────────┐    ┌─────────────────────────┐    ┌─────────────────────────┐
│     Infrastructure      │    │      Supply Chain       │    │     Communications      │
│  Datadog, AWS, Grafana  │    │      SAP, NetSuite      │    │     Slack, Zoom, Meet   │
├─────────────────────────┤    ├─────────────────────────┤    ├─────────────────────────┤
│ Sees: Service 500 errors│    │ Sees: Static inventory  │    │ Sees: Verbal delays &   │
│ Goal: Restart payments  │    │ Goal: Maintain buffer   │    │       unowned tasks     │
└────────────┬────────────┘    └────────────┬────────────┘    └────────────┬────────────┘
             │                              │                              │
             └──────────────────────┬───────┴──────────────────────────────┘
                                    ▼
                     THE CROSS-DOMAIN BLIND SPOT
          "Fixing the payment gateway flushes trapped orders,
          which immediately causes a catastrophic stockout."
```

When an engineering team restarts an unresponsive payment service, they optimize locally. However, if supplier delivery is delayed by 5 days (a fact only mentioned in a management meeting transcript) and trapped payment retries consume the remaining stock, the technical "fix" crashes inventory coverage from 1.5 days down to 0.9 days.

No single dashboard connects these dots. **NEXUS solves this by correlating evidence across all domains into a unified risk graph.**

---

## Our Solution

NEXUS bridges operational silos through an end-to-end intelligence and execution lifecycle:

1. **Multi-Source Ingestion & Normalization**: Converts unstructured text logs, JSONL streams, CSV spreadsheets, and meeting transcripts into a standardized typed event schema.
2. **Deterministic & Agentic Analysis**: Evaluates failure signatures and supplier timelines using deterministic mathematics (zero hallucination risk), backed by constrained LLMs for transcript comprehension.
3. **Cross-Domain Correlation Engine**: Connects infrastructure failures, communication commitments, and inventory demand to evaluate system-wide blast radius.
4. **Governed Response Planning**: Generates prioritized mitigation actions (e.g., procurement of alternative supplier inventory, rate-limited traffic pacing, service rollbacks).
5. **Human-in-the-Loop Policy Engine**: Enforces role-based permissions (RBAC) and spending limit policies (`NEXUS_PO_ADMIN_THRESHOLD`) before any action executes.
6. **Cryptographic Auditability**: Anchors all decisions, approvals, and system state transitions into an immutable, SHA-256 hash-chained audit log.
7. **Closed-Loop Verification**: Re-evaluates live telemetry post-recovery to verify whether the executed actions resolved the coverage gap.

---

## Key Features

### Implemented & Production-Ready
- **Decoupled LangGraph State Machines**: Separate state machines for investigation and recovery so workflows survive service restarts without dangling processes.
- **Specialized Multi-Agent Swarm**: Four domain agents (Infrastructure, Communication, Supply, and Execution) running deterministic tools and emitting structured evidence.
- **Cross-Domain Correlation Graph**: Interactive dependency visualization linking service nodes, supplier entities, and human action items.
- **Evidence-Backed Attribution**: Every finding, claim, and recommendation links directly to its source locator (`file.log line 42`, CSV row, or audio transcript timestamp).
- **Dual Execution Engine (LLM + Deterministic Fallback)**: Runs with OpenAI models (`gpt-4o-mini`) when configured, or executes complete rule-based extraction and template generation without any API key required.
- **Policy Engine with Spending Escalation**: Automatic checks on action risk, financial limits (default \$5,000 threshold requires Admin), and confidence gates.
- **Tamper-Evident SHA-256 Audit Trail**: Cryptographic blockchain-like audit trail with automated genesis block creation and real-time chain validation.
- **Role-Based Access Control (RBAC)**: Distinct permission tiers for `viewer`, `analyst`, `approver`, and `admin`.
- **Closed-Loop Verification**: Upload subsequent post-recovery telemetry to automatically prove that interventions resolved the incident.

### Architecture & Governance Roadmap
- Real cloud connectors for automated execution (AWS ECS, Kubernetes, Stripe, SAP ERP).
- Distributed queue integration (Celery / Redis) for horizontal multi-worker scaling.
- Webhook subscriptions and streaming alerts (PagerDuty, Slack, OpsGenie).

---

## System Architecture

```mermaid
flowchart TD
    subgraph UI ["User Interface (React 19 + TypeScript + Vite)"]
        CC[Command Center]
        AW[Agent Workspace]
        IG[Intelligence Graph]
        RC[Response Center]
        AT[Audit Trail]
    end

    subgraph API ["FastAPI Application Layer (Python 3.12+ / 3.14)"]
        AUTH[Auth & RBAC Middleware]
        INGEST[Ingestion & Normalizer]
        ROUTES[REST API Endpoints]
        POLICY[Policy Engine]
        AUDIT[Audit Service & Hash Chain]
    end

    subgraph LG ["LangGraph Orchestration Framework"]
        TRIAGE[Triage Node]
        
        subgraph AGENTS ["Specialist Domain Agents"]
            IA[Infrastructure Agent]
            CA[Communication Agent]
            SA[Supply Agent]
            EA[Execution Agent]
        end
        
        CORR[Correlation Engine]
        PLAN[Planning Engine]
        POL_NODE[Policy Check Node]
        FIN[Finalize & State Persist]
    end

    subgraph RECOVERY ["Recovery Workflow"]
        EXEC[Controlled Execution]
        VERIF[Outcome Verification]
        STATUS[Status Refresh]
    end

    subgraph DATA ["Persistence & State Layer"]
        DB[(SQLite / PostgreSQL)]
        AUDIT_LOG[(Append-Only Hash Chain)]
    end

    UI -->|JWT Authenticated Requests| AUTH
    AUTH --> ROUTES
    ROUTES --> INGEST
    INGEST -->|Normalized Events| DB
    ROUTES -->|Trigger Background Task| TRIAGE

    TRIAGE --> IA & CA & SA & EA
    IA & CA & SA & EA --> CORR
    CORR --> PLAN
    PLAN --> POL_NODE
    POL_NODE --> FIN
    FIN --> DB

    RC -->|Approve Action| POLICY
    POLICY --> EXEC
    EXEC --> VERIF
    VERIF --> STATUS
    STATUS --> DB

    AUDIT --> AUDIT_LOG
```

---

## Multi-Agent Architecture

NEXUS coordinates four specialist agents via LangGraph. Each agent calls deterministic tools and yields structured findings. Agents do not communicate directly with one another; the orchestrator router governs execution sequence:

| Agent | Input Domain | Tools Called | Output Findings |
|---|---|---|---|
| **Infrastructure Agent** | Infrastructure logs, service topology | `log_correlator` | Identifies failing services, error spikes, suspect deploy events, and blast-radius propagation across dependencies. |
| **Communication Agent** | Meeting transcripts, audio logs | `transcript_extractor` | Extracts speaker commitments, confirmed vendor delays, and unowned action items using strict verbatim quoting. |
| **Supply Agent** | Inventory snapshots, supplier catalogs, incident backlog | `stockout_calculator`, `supplier_comparison` | Computes days of stock cover, stockout timelines, revenue-at-risk, and compares alternative supplier options. |
| **Execution Agent** | Task records, meeting action items | `ownership_checker` | Audits open tasks, highlights unassigned critical work, and correlates deadlines with incident milestones. |

---

## Technology Stack

### Frontend
- **Framework**: React 19 (Hooks, StrictMode)
- **Language**: TypeScript 5.8
- **Tooling & Bundler**: Vite 7
- **Styling**: Tailwind CSS
- **Icons**: Inline SVG components (`src/ui.tsx`)
- **HTTP Client**: Native Fetch API with typed wrappers

### Backend
- **Framework**: FastAPI 0.115+
- **ASGI Server**: Uvicorn 0.54+
- **Runtime**: Python 3.12+ (fully verified on Python 3.14.3)
- **Validation**: Pydantic v2 & Pydantic-Settings
- **ORM & Database**: SQLAlchemy 2.0 with unified SQLite & PostgreSQL support (`psycopg` 3.3 binary)
- **Authentication**: PyJWT (HS256) & PBKDF2-HMAC-SHA256 password security

### AI & Agentic Orchestration
- **Agent Orchestrator**: LangGraph 1.2+ & LangChain Core 1.7+
- **LLM Integration**: OpenAI API (`gpt-4o-mini`) with deterministic fallback engines
- **Audit System**: Cryptographic SHA-256 linked blocks with verified integrity checks

### DevOps & Infrastructure
- **Containerization**: Docker & Docker Compose
- **Web Server (Production UI)**: Nginx (Alpine)
- **CI/CD Pipeline**: GitHub Actions (multi-matrix database testing on Python 3.14 + Node 24)
- **Linter & Formatter**: Ruff

---

## Project Structure

```text
NEXUS/
├── .github/
│   └── workflows/
│       └── ci.yml                 # Multi-job GitHub Actions CI (Backend matrix, Frontend, Docker)
├── .claude/
│   └── launch.json                # Local debugging definitions
├── backend/
│   ├── app/
│   │   ├── orchestrator/          # LangGraph state machines & multi-agent definitions
│   │   │   ├── agents.py          # 4 specialist domain agents (Incident, Comm, Supply, Exec)
│   │   │   ├── correlate.py       # Cross-domain correlation, blast radius & planning logic
│   │   │   ├── graph.py           # Investigation & Recovery StateGraph compilations
│   │   │   └── state.py           # TypedDict definitions for graph states
│   │   ├── services/              # Business logic & domain computation engines
│   │   │   ├── approval_service.py # Action approval, execution & verification logic
│   │   │   ├── audit.py           # SHA-256 cryptographic audit chain engine
│   │   │   ├── business_service.py # Deterministic stockout & supplier calculations
│   │   │   ├── communication_service.py # Verbatim transcript extraction
│   │   │   ├── evidence_service.py # Citation generation & tracking
│   │   │   ├── incident_service.py # Log clustering, deploy correlation & blast radius
│   │   │   ├── ingestion.py       # File size/type validation & tenant persistence
│   │   │   ├── llm.py             # OpenAI client with structured parsing & prompt guardrails
│   │   │   ├── normalizer.py      # Common event schema converter for logs, CSVs, txt
│   │   │   ├── policy_engine.py   # Spending threshold & role authorization rules
│   │   │   └── report_service.py  # Markdown & JSON post-incident report builder
│   │   ├── api.py                 # Tenant-scoped REST API route controllers
│   │   ├── config.py              # Environment configuration & pydantic settings
│   │   ├── db.py                  # Database engine, connection pooling & session management
│   │   ├── main.py                # FastAPI initialization, CORS & startup routines
│   │   ├── models.py              # SQLAlchemy relational schema models (12 tables)
│   │   ├── schemas.py             # Pydantic request/response validation schemas
│   │   └── security.py            # Password hashing, JWT creation & RBAC dependencies
│   ├── tests/
│   │   ├── conftest.py            # Pytest fixtures, test client & tenant setup
│   │   ├── test_platform.py       # End-to-end API, RBAC, policy & graph integration tests
│   │   └── test_units.py          # Unit tests for normalizer, stockout math & audit hash chain
│   ├── Dockerfile                 # Python 3.14 container image build
│   ├── pyproject.toml             # Pytest & Ruff tool configurations
│   ├── requirements.txt           # Core production dependencies
│   └── requirements-dev.txt       # Development & testing dependencies
├── demo_data/
│   ├── checkout-platform.log      # Synthetic infrastructure logs showing payment service error
│   ├── dependencies.csv           # Architecture service topology
│   ├── inventory.csv              # Initial stock levels & daily demand
│   ├── ops-bridge-transcript.txt  # Incident response meeting transcript with vendor delay
│   ├── suppliers.csv              # Alternative supplier costs & lead times
│   ├── tasks.csv                  # Open team action items & ownership tracking
│   └── post_recovery/
│       ├── inventory-update.csv   # Post-incident stock update for closed-loop verification
│       └── payment-recovery.log   # Telemetry proving service restoration
├── frontend/
│   ├── src/
│   │   ├── screens/               # React application screens
│   │   │   ├── AgentWorkspace.tsx # Live agent step inspector & tool invocation viewer
│   │   │   ├── AuditTrail.tsx     # Verifiable cryptographic audit log explorer
│   │   │   ├── CommandCenter.tsx  # Executive incident summary & risk score overview
│   │   │   ├── DataIngestion.tsx  # Multi-file uploader & demo scenario loader
│   │   │   ├── EvidenceViewer.tsx # Interactive source attribution & excerpt explorer
│   │   │   ├── History.tsx        # Past incident archive & timeline
│   │   │   ├── IntelligenceGraph.tsx # Force-directed cross-domain dependency graph
│   │   │   ├── Login.tsx          # Authentication & tenant organization switcher
│   │   │   ├── ReportView.tsx     # Executive post-mortem report renderer & MD exporter
│   │   │   ├── ResponseCenter.tsx # Governed approval action queue & decision controls
│   │   │   └── Workspace.tsx      # Project management & team member administration
│   │   ├── api.ts                 # Typed backend API client
│   │   ├── App.tsx                # Main router, navigation header & state provider
│   │   ├── main.tsx               # React DOM entry point
│   │   └── ui.tsx                 # Reusable UI component library (Badges, Cards, Modals)
│   ├── Dockerfile                 # Multi-stage production build with Nginx
│   ├── nginx.conf                 # SPA routing & reverse proxy configuration
│   ├── package.json               # Node dependencies & build scripts
│   └── vite.config.ts             # Vite build & development server configuration
├── .dockerignore
├── .env.example                   # Environment configuration template
├── .gitignore                     # Git hygiene exclusions
├── docker-compose.yml             # Full-stack composition (API, Frontend, PostgreSQL)
├── LICENSE                        # MIT Open Source License
├── README.md                      # Comprehensive project documentation
└── start.ps1                      # Windows automated local launcher script
```

---

## Getting Started

### Prerequisites
- **Python**: Version 3.12 or newer (verified on Python 3.14)
- **Node.js**: Version 20 or newer (npm 10+)
- **Git**
- *Optional*: Docker & Docker Compose

---

### Method 1: Automated Local Setup (Windows)

From PowerShell in the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

This script automatically:
1. Configures the Python virtual environment (`backend/.venv`) and installs `requirements-dev.txt`.
2. Installs frontend dependencies (`npm install`).
3. Launches the Backend API on port `8000`.
4. Launches the Vite development server on port `5173`.
5. Opens your default web browser to [http://localhost:5173](http://localhost:5173).

---

### Method 2: Manual Step-by-Step Setup

#### 1. Clone the Repository
```bash
git clone https://github.com/SUBHA22-CODER/NEXUS.git
cd NEXUS
```

#### 2. Configure Backend
```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt

# Start backend server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
*Backend Swagger documentation is available at:* [http://localhost:8000/docs](http://localhost:8000/docs)

#### 3. Configure Frontend
In a new terminal window:
```bash
cd frontend

# Install packages
npm install

# Start Vite dev server
npm run dev -- --host 0.0.0.0
```
*Frontend interface is available at:* [http://localhost:5173](http://localhost:5173)

---

### Method 3: Run with Docker Compose

Run the complete multi-container stack (Backend, Frontend, and PostgreSQL):

```bash
cp .env.example .env
# Set NEXUS_JWT_SECRET and POSTGRES_PASSWORD in .env

docker compose up --build
```
Access the application at [http://localhost:8080](http://localhost:8080).

---

## Environment Variables

Copy `.env.example` to `.env` or set these in your hosting environment:

| Variable | Default Value | Description |
|---|---|---|
| `NEXUS_ENV` | `dev` | Environment mode (`dev`, `test`, or `production`). Demo ingestion is disabled in `production`. |
| `NEXUS_JWT_SECRET` | *(auto-generated in dev)* | Cryptographic key for signing HS256 auth tokens. **Must be explicitly set in production.** |
| `NEXUS_DATABASE_URL` | `sqlite:///./nexus.db` | Database connection string. Use `postgresql+psycopg://user:pass@host:5432/db` for Postgres. |
| `NEXUS_PO_ADMIN_THRESHOLD` | `5000` | Financial spending limit ($). Actions exceeding this amount require `admin` role approval. |
| `MAX_UPLOAD_SIZE_MB` | `25` | Maximum file upload size in megabytes (configurable per environment, default: 25 MB). |
| `OPENAI_API_KEY` | *(optional)* | OpenAI API key. If omitted, NEXUS seamlessly uses its deterministic rule engines. |
| `NEXUS_OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model identifier when LLM mode is enabled. |
| `POSTGRES_PASSWORD` | *(empty)* | Database password used by `docker-compose.yml`. |

---

## The Demo Scenario Walkthrough

The repository includes a battle-tested synthetic demonstration scenario located in `demo_data/`:

| Dimension | Isolated View | Cross-Domain Reality Discovered by NEXUS |
|---|---|---|
| **Inventory Metric** | 15 units on hand; regular supplier delivery expected today. | Initial stock cover: **1.5 days** (Daily demand = 10 units/day). |
| **Meeting Transcript** | Management discusses a vendor logistics disruption. | Supplier shipment is delayed **5 days**. Supply gap becomes **3.5 days**. |
| **Infrastructure Logs** | Payment gateway throwing 500 errors; requests queueing up. | **6 units** worth of customer orders are stuck behind the payment failure. |
| **The Collision Trap** | *If payments are blindly restored...* | Backlog flushes instantly: effective stock drops from 15 to **9 units**. Coverage drops to **0.9 days**, expanding the supply gap to **4.1 days**. |

### Step-by-Step Walkthrough in the UI:
1. Open [http://localhost:5173](http://localhost:5173).
2. Register an account (automatically granted `admin` privileges).
3. Create a project named **Checkout**.
4. Go to **Data Ingestion** $\rightarrow$ Click **Load demo scenario**.
5. Navigate to the **Command Center** $\rightarrow$ Click **Run Investigation**.
6. Observe the LangGraph multi-agent pipeline executing live in the **Agent Workspace**.
7. Inspect the **Intelligence Graph** to see the cross-domain correlation.
8. Go to the **Response Center** to review, approve, or reject proposed recovery recommendations.
9. To test closed-loop verification: Go to **Data Ingestion** $\rightarrow$ Click **Load post-recovery data** $\rightarrow$ Click **Check outcomes**.

---

## API Reference

All API routes are tenant-scoped under the `/api` prefix. Requests must include the `Authorization: Bearer <token>` header (except auth endpoints).

### Authentication & Users
- `POST /api/auth/register` — Register a new tenant organization and admin user.
- `POST /api/auth/login` — Authenticate and receive a JWT access token.
- `GET /api/me` — Retrieve current user profile, role, and system capabilities.
- `GET /api/users` — List organization members (*Admin only*).
- `POST /api/users` — Provision new user with specific role (*Admin only*).

### Projects & Ingestion
- `GET /api/projects` — List organization projects.
- `POST /api/projects` — Create an operational workspace project (*Analyst+*).
- `POST /api/projects/{id}/uploads` — Upload operational datasets (supports `.csv, .tsv, .txt, .log, .json, .jsonl, .md`, up to 25 MB) (*Analyst+*).
- `GET /api/projects/{id}/files` — List all uploaded datasets with metadata and processing statuses.
- `GET /api/projects/{id}/files/{file_id}` — View uploaded file details and sample parsed events.
- `DELETE /api/projects/{id}/files/{file_id}` — Delete an uploaded file and cascade delete its events (*Analyst+*).
- `POST /api/projects/{id}/demo` — Ingest bundled synthetic demo datasets (*Analyst+*).
- `GET /api/projects/{id}/events` — Query normalized operational events.
- `GET /api/projects/{id}/overview` — Retrieve high-level operational health and active risks.

### Investigations & Multi-Agent Graph
- `POST /api/projects/{id}/investigations` — Dispatch background LangGraph investigation (*Analyst+*).
- `GET /api/incidents/{id}` — Retrieve full incident investigation state, findings, and confidence score.
- `GET /api/incidents/{id}/agent-runs` — Inspect tool invocations, timing, and agent statuses.
- `GET /api/incidents/{id}/graph` — Retrieve interactive dependency nodes and correlation edges.
- `GET /api/incidents/{id}/evidence` — List cited evidence items and source references.
- `GET /api/incidents/{id}/report` — Export executive summary (`json` or downloadable `markdown`).

### Response, Governance & Verification
- `GET /api/incidents/{id}/recommendations` — List proposed recovery actions with policy verdicts.
- `POST /api/recommendations/{id}/decision` — Approve or reject an action (*Approver+ / Admin*).
- `POST /api/incidents/{id}/verify` — Re-evaluate live data to verify recovery (*Analyst+*).
- `GET /api/audit` — Query the immutable SHA-256 cryptographic audit chain (*Approver+*).

---

## Testing & Quality Verification

NEXUS enforces continuous testing across backend services, agents, mathematical formulas, and the frontend build.

### Run Backend Tests
From the `backend/` directory:
```bash
pytest -v
```
**Test Results (57 passed):**
- `tests/test_platform.py`: Full API lifecycle, tenant isolation, RBAC role escalation, policy thresholds, and LangGraph workflow runs.
- `tests/test_units.py`: Deterministic stockout math, supplier comparison algorithms, normalizer parsers, and SHA-256 audit chain tamper detection.

### Run Frontend Typecheck & Build
From the `frontend/` directory:
```bash
npm run build
```
Executes TypeScript compilation (`tsc --noEmit`) and Vite production bundling (`vite build`) with zero errors.

### Continuous Integration
GitHub Actions automatically executes the complete matrix on every push to `main` and all pull requests:
- **Backend Matrix**: Tests across both SQLite and real PostgreSQL 16 containers.
- **Frontend Job**: Verifies clean dependency install (`npm ci`) and production build.
- **Image Job**: Validates Docker container builds for both services.

---

## Security & Governance

1. **Role-Based Access Control (RBAC)**:
   - `viewer`: Read-only access to dashboards, graphs, and reports.
   - `analyst`: Can upload data, trigger investigations, and update action tasks.
   - `approver`: Can approve operational decisions and purchase orders up to `$5,000`.
   - `admin`: Can execute critical production rollbacks, approve large purchases, and manage users.

2. **Policy Enforcement Engine**:
   - Every recommendation proposed by an agent is evaluated by `policy_engine.py`.
   - Actions with high blast radius or exceeding financial limits are blocked or escalated to administrative roles.

3. **Tamper-Evident SHA-256 Audit Chain**:
   - Every critical event (user creation, data upload, investigation run, approval decision) is hashed:
     $$\text{Hash}_n = \text{SHA-256}(\text{Sequence} \parallel \text{Actor} \parallel \text{Action} \parallel \text{Detail} \parallel \text{Hash}_{n-1})$$
   - The `/api/audit` endpoint runs continuous cryptographic verification across the full chain to detect tampering or deleted records.

4. **Closed-Loop Outcome Verification**:
   - Rather than assuming an approved action worked, the recovery engine re-evaluates post-recovery telemetry against the initial hypothesis to confirm actual resolution.

---

## Engineering Audit

A full production-readiness audit (reconnaissance, baseline, testing, security, performance, and readiness scorecard) lives in [`docs/`](docs/):

- [`PROJECT_AUDIT.md`](docs/PROJECT_AUDIT.md) — architecture and current-state findings
- [`TESTING_STRATEGY.md`](docs/TESTING_STRATEGY.md) — test plan and gaps
- [`TEST_RESULTS.md`](docs/TEST_RESULTS.md) — executed commands and real outputs
- [`SECURITY_AUDIT.md`](docs/SECURITY_AUDIT.md) — severity-classified security findings
- [`PERFORMANCE_REPORT.md`](docs/PERFORMANCE_REPORT.md) — measured numbers
- [`KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) and [`BUG_FIX_LOG.md`](docs/BUG_FIX_LOG.md) — gaps and fixes
- [`PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md) — readiness scorecard

## Contributing & License

Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/amazing-feature`.
3. Commit your changes following conventional commit syntax: `git commit -m 'feat: add amazing feature'`.
4. Ensure all tests pass: `pytest` and `npm run build`.
5. Push to the branch: `git push origin feature/amazing-feature`.
6. Open a Pull Request.

### License
This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
