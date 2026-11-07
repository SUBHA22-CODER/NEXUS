"""HTTP API. Every lookup is tenant-scoped: another organization's id behaves exactly like a missing one."""
import os
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import AgentRun, AuditLog, Evidence, Incident, OperationalEvent, Project, Recommendation, Task, Tenant, UploadedFile, User
from .orchestrator.graph import run_investigation, run_recovery
from .rate_limit import LOGIN, REGISTER, gate
from .schemas import DecisionIn, LoginIn, ProjectIn, RegisterIn, TaskPatchIn, UserCreateIn
from .security import DUMMY_HASH, create_token, current_user, hash_password, require_role, verify_password
from .services import approval_service, audit, ingestion, llm, report_service

router = APIRouter(prefix="/api")
DEMO_DIR = Path(os.environ.get("NEXUS_DEMO_DIR", Path(__file__).resolve().parents[2] / "demo_data"))
DEMO_FILES = {
    "initial": ["dependencies.csv", "checkout-platform.log", "inventory.csv", "suppliers.csv", "tasks.csv", "ops-bridge-transcript.txt"],
    "recovery": ["post_recovery/payment-recovery.log", "post_recovery/inventory-update.csv"],
    "supply_chain": ["dependencies.csv", "checkout-platform.log", "inventory.csv", "suppliers.csv", "tasks.csv", "ops-bridge-transcript.txt"],
    "it_ops": ["it_dependencies.csv", "it_operations.log"],
    "security": ["cybersecurity_events_demo.csv"],
    "finance": ["finance_transactions_demo.csv"],
    "manufacturing": ["manufacturing_production_demo.csv"],
    "all": [
        "dependencies.csv", "checkout-platform.log", "inventory.csv", "suppliers.csv", "tasks.csv", "ops-bridge-transcript.txt",
        "cybersecurity_events_demo.csv", "finance_transactions_demo.csv", "manufacturing_production_demo.csv",
    ],
}


def _owned(db: Session, model, row_id: uuid.UUID, user: User):
    row = db.get(model, row_id)
    if row is None or row.tenant_id != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} not found")
    return row


def _user_out(u: User) -> dict:
    return {"id": str(u.id), "name": u.name, "email": u.email, "role": u.role}


def _project_out(p: Project) -> dict:
    return {"id": str(p.id), "name": p.name, "description": p.description, "created_at": p.created_at.isoformat()}


def _incident_out(i: Incident, *, full: bool = False) -> dict:
    out = {
        "id": str(i.id), "project_id": str(i.project_id), "title": i.title, "status": i.status, "severity": i.severity, "risk_score": i.risk_score,
        "summary": i.summary, "narrative_method": i.narrative_method, "error": i.error, "created_at": i.created_at.isoformat(), "updated_at": i.updated_at.isoformat(),
    }
    if full:
        state = i.state or {}
        out.update({k: state.get(k, []) for k in ("findings", "hypotheses", "uncertainties", "supply_assessments", "unowned_work", "active_agents", "security_assessments", "finance_assessments", "manufacturing_assessments")})
        out["confidence"] = state.get("confidence")
        out["event_count"] = state.get("event_count", 0)
    return out


def _rec_out(r: Recommendation, approval: dict | None = None) -> dict:
    return {
        "id": str(r.id), "incident_id": str(r.incident_id), "action_type": r.action_type, "title": r.title, "rationale": r.rationale, "domain": r.domain,
        "priority": r.priority, "risk_level": r.risk_level, "confidence": r.confidence, "required_role": r.required_role, "status": r.status, "params": r.params,
        "evidence_ids": r.evidence_ids, "policy_result": r.policy_result, "execution": r.execution, "verification": r.verification,
        "executed_at": r.executed_at.isoformat() if r.executed_at else None, "approval": approval,
    }


def _task_out(t: Task) -> dict:
    return {"id": str(t.id), "incident_id": str(t.incident_id) if t.incident_id else None, "title": t.title, "owner": t.owner, "deadline": t.deadline, "status": t.status, "recommendation_id": str(t.recommendation_id) if t.recommendation_id else None}


# ---- Auth and workspace -------------------------------------------------------------------------

@router.post("/auth/register", status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    gate(REGISTER, request.client.host if request.client else "unknown")
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    tenant = Tenant(name=body.organization)
    db.add(tenant)
    db.flush()
    user = User(tenant_id=tenant.id, email=email, name=body.name, role="admin", password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists") from None
    audit.record(db, tenant.id, email, "organization.created", "tenant", tenant.id, {"name": body.organization})
    db.commit()
    return {"token": create_token(user), "user": _user_out(user), "organization": tenant.name}


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    gate(LOGIN, f"{request.client.host if request.client else 'unknown'}:{body.email.lower()}")
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    valid = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    tenant = db.get(Tenant, user.tenant_id)
    return {"token": create_token(user), "user": _user_out(user), "organization": tenant.name}


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    tenant = db.get(Tenant, user.tenant_id)
    settings = get_settings()
    return {
        "user": _user_out(user),
        "organization": tenant.name,
        "llm_enabled": llm.available(),
        "demo_enabled": settings.demo_enabled,
        "max_upload_bytes": settings.max_upload_bytes,
        "max_upload_size_mb": settings.max_upload_size_mb,
    }


@router.get("/users")
def list_users(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return [_user_out(u) for u in db.scalars(select(User).where(User.tenant_id == user.tenant_id).order_by(User.created_at))]


@router.post("/users", status_code=201)
def create_user(body: UserCreateIn, user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    created = User(tenant_id=user.tenant_id, email=email, name=body.name, role=body.role, password_hash=hash_password(body.password))
    db.add(created)
    db.flush()
    audit.record(db, user.tenant_id, user.email, "user.created", "user", created.id, {"email": email, "role": body.role})
    db.commit()
    return _user_out(created)


@router.get("/projects")
def list_projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [_project_out(p) for p in db.scalars(select(Project).where(Project.tenant_id == user.tenant_id).order_by(Project.created_at))]


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, user: User = Depends(require_role("analyst")), db: Session = Depends(get_db)):
    project = Project(tenant_id=user.tenant_id, name=body.name, description=body.description)
    db.add(project)
    db.flush()
    audit.record(db, user.tenant_id, user.email, "project.created", "project", project.id, {"name": body.name})
    db.commit()
    return _project_out(project)


# ---- Ingestion -----------------------------------------------------------------------------------

@router.post("/projects/{project_id}/uploads")
async def upload_files(project_id: uuid.UUID, files: list[UploadFile] = File(...), user: User = Depends(require_role("analyst")), db: Session = Depends(get_db)):
    _owned(db, Project, project_id, user)
    limit = get_settings().max_upload_bytes
    results = []
    for upload in files:
        # Reads one byte past the limit so an oversized file is refused without loading all of it.
        content = await upload.read(limit + 1)
        filename = upload.filename or "unknown"
        try:
            results.append(ingestion.ingest_bytes(db, user, project_id, filename, content))
            db.commit()
        except ingestion.IngestionError as exc:
            db.rollback()
            # Record failed file metadata for transparency
            try:
                ingestion.record_failed_file(db, user, project_id, filename, len(content), str(exc))
                db.commit()
            except Exception:
                db.rollback()
            results.append({"file": filename, "error": str(exc)})
    return {"results": results}


@router.get("/projects/{project_id}/files")
def list_files(project_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _owned(db, Project, project_id, user)
    files = db.scalars(
        select(UploadedFile)
        .where(UploadedFile.project_id == project_id, UploadedFile.tenant_id == user.tenant_id)
        .order_by(UploadedFile.created_at.desc())
    ).all()
    return [
        {
            "id": str(f.id),
            "filename": f.filename,
            "file_type": f.file_type,
            "file_size": f.file_size,
            "status": f.status,
            "events_count": f.events_count,
            "dependencies_count": f.dependencies_count,
            "error_message": f.error_message,
            "created_by": f.created_by,
            "created_at": f.created_at.isoformat(),
        }
        for f in files
    ]


@router.get("/projects/{project_id}/files/{file_id}")
def get_file(project_id: uuid.UUID, file_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _owned(db, Project, project_id, user)
    f = db.get(UploadedFile, file_id)
    if not f or f.project_id != project_id or f.tenant_id != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    events = db.scalars(
        select(OperationalEvent)
        .where(OperationalEvent.project_id == project_id, OperationalEvent.source_file == f.filename)
        .order_by(OperationalEvent.occurred_at.desc())
        .limit(100)
    ).all()
    return {
        "file": {
            "id": str(f.id),
            "filename": f.filename,
            "file_type": f.file_type,
            "file_size": f.file_size,
            "status": f.status,
            "events_count": f.events_count,
            "dependencies_count": f.dependencies_count,
            "error_message": f.error_message,
            "created_by": f.created_by,
            "created_at": f.created_at.isoformat(),
        },
        "sample_events": [
            {
                "id": str(e.id),
                "domain": e.domain,
                "event_type": e.event_type,
                "severity": e.severity,
                "summary": e.summary,
                "occurred_at": e.occurred_at.isoformat(),
                "locator": e.source_locator,
            }
            for e in events
        ],
    }


@router.delete("/projects/{project_id}/files/{file_id}")
def delete_file(project_id: uuid.UUID, file_id: uuid.UUID, user: User = Depends(require_role("analyst")), db: Session = Depends(get_db)):
    _owned(db, Project, project_id, user)
    success = ingestion.delete_uploaded_file(db, user, project_id, file_id)
    if not success:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return {"ok": True, "deleted_id": str(file_id)}


@router.post("/projects/{project_id}/demo")
def load_demo(project_id: uuid.UUID, stage: Literal["initial", "recovery"] = "initial", environment: Literal["supply_chain", "it_ops", "security", "finance", "manufacturing", "all"] | None = None, user: User = Depends(require_role("analyst")), db: Session = Depends(get_db)):
    if not get_settings().demo_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo data is not available")
    _owned(db, Project, project_id, user)
    results = []
    for rel in DEMO_FILES[environment or stage]:
        path = DEMO_DIR / rel
        results.append(ingestion.ingest_bytes(db, user, project_id, path.name, path.read_bytes()))
    db.commit()
    return {"results": results}


@router.get("/projects/{project_id}/events")
def list_events(project_id: uuid.UUID, domain: str | None = None, limit: int = 200, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _owned(db, Project, project_id, user)
    query = select(OperationalEvent).where(OperationalEvent.project_id == project_id, OperationalEvent.tenant_id == user.tenant_id)
    if domain:
        query = query.where(OperationalEvent.domain == domain)
    rows = db.scalars(query.order_by(OperationalEvent.occurred_at.desc()).limit(min(max(limit, 1), 1000)))
    return [
        {"id": str(e.id), "domain": e.domain, "event_type": e.event_type, "severity": e.severity, "occurred_at": e.occurred_at.isoformat(), "entity": e.entity, "summary": e.summary, "source_file": e.source_file, "source_locator": e.source_locator}
        for e in rows
    ]


@router.get("/projects/{project_id}/overview")
def overview(project_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _owned(db, Project, project_id, user)
    domain_counts = dict(db.execute(select(OperationalEvent.domain, func.count()).where(OperationalEvent.project_id == project_id).group_by(OperationalEvent.domain)).all())
    incidents = db.scalars(select(Incident).where(Incident.project_id == project_id).order_by(Incident.created_at.desc()).limit(20)).all()
    latest = next((i for i in incidents if i.status not in ("running", "failed")), None)
    pending = db.scalar(
        select(func.count()).select_from(Recommendation).join(Incident, Recommendation.incident_id == Incident.id).where(Incident.project_id == project_id, Recommendation.status == "proposed")
    )
    open_tasks = db.scalar(select(func.count()).select_from(Task).where(Task.project_id == project_id, Task.status != "done"))
    risks = [a for a in (latest.state.get("supply_assessments", []) if latest else []) if a["current"]["risk_level"] != "low" or a["worst_case"]["risk_level"] != "low"]
    return {
        "event_counts": domain_counts,
        "pending_approvals": pending,
        "open_tasks": open_tasks,
        "active_investigations": sum(1 for i in incidents if i.status == "running"),
        "incidents": [_incident_out(i) for i in incidents],
        "latest": _incident_out(latest, full=True) if latest else None,
        "business_risks": risks,
    }


# ---- Investigations -------------------------------------------------------------------------------

@router.post("/projects/{project_id}/investigations", status_code=202)
def start_investigation(project_id: uuid.UUID, background: BackgroundTasks, request: Request, user: User = Depends(require_role("analyst")), db: Session = Depends(get_db)):
    _owned(db, Project, project_id, user)
    if not db.scalar(select(func.count()).select_from(OperationalEvent).where(OperationalEvent.project_id == project_id)):
        raise HTTPException(422, "Upload some data before starting an investigation")
    if db.scalar(select(Incident.id).where(Incident.project_id == project_id, Incident.status == "running")):
        raise HTTPException(status.HTTP_409_CONFLICT, "An investigation is already running in this project")
    incident = Incident(tenant_id=user.tenant_id, project_id=project_id, created_by=user.id)
    db.add(incident)
    db.flush()
    audit.record(db, user.tenant_id, user.email, "investigation.started", "incident", incident.id, {"request_id": getattr(request.state, "request_id", None)})
    db.commit()
    background.add_task(run_investigation, incident.id)
    return _incident_out(incident)


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _incident_out(_owned(db, Incident, incident_id, user), full=True)


@router.get("/incidents/{incident_id}/agent-runs")
def agent_runs(incident_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _owned(db, Incident, incident_id, user)
    rows = db.scalars(select(AgentRun).where(AgentRun.incident_id == incident_id).order_by(AgentRun.sequence))
    return [
        {"id": str(r.id), "agent": r.agent, "status": r.status, "sequence": r.sequence, "note": r.note, "method": r.method, "error": r.error, "tool_calls": r.tool_calls, "findings": r.findings,
         "started_at": r.started_at.isoformat(), "finished_at": r.finished_at.isoformat() if r.finished_at else None}
        for r in rows
    ]


@router.get("/incidents/{incident_id}/graph")
def incident_graph(incident_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    incident = _owned(db, Incident, incident_id, user)
    nodes: dict[str, dict] = {}
    edges = []
    for h in (incident.state or {}).get("hypotheses", []):
        for name, domain in ((h["source"], h["source_domain"]), (h["target"], h["target_domain"])):
            nodes.setdefault(name, {"id": name, "label": name, "domain": domain})
        edges.append({k: h[k] for k in ("source", "target", "relation", "explanation", "status", "confidence", "evidence_ids")})
    return {"nodes": list(nodes.values()), "edges": edges}


@router.get("/incidents/{incident_id}/evidence")
def incident_evidence(incident_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _owned(db, Incident, incident_id, user)
    rows = db.scalars(select(Evidence).where(Evidence.incident_id == incident_id).order_by(Evidence.created_at))
    return [
        {"id": str(e.id), "kind": e.kind, "domain": e.domain, "claim": e.claim, "excerpt": e.excerpt, "source_file": e.source_file, "source_locator": e.source_locator}
        for e in rows
    ]


@router.get("/incidents/{incident_id}/recommendations")
def incident_recommendations(incident_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from .models import Approval

    _owned(db, Incident, incident_id, user)
    recs = db.scalars(select(Recommendation).where(Recommendation.incident_id == incident_id).order_by(Recommendation.priority, Recommendation.created_at)).all()
    approvals = {
        a.recommendation_id: {"decision": a.decision, "comment": a.comment, "by": name, "at": a.created_at.isoformat()}
        for a, name in db.execute(select(Approval, User.name).join(User, Approval.decided_by == User.id).where(Approval.recommendation_id.in_([r.id for r in recs])))
    }
    return [_rec_out(r, approvals.get(r.id)) for r in recs]


@router.post("/recommendations/{rec_id}/decision")
def decide(rec_id: uuid.UUID, body: DecisionIn, user: User = Depends(require_role("approver")), db: Session = Depends(get_db)):
    rec = _owned(db, Recommendation, rec_id, user)
    rec = approval_service.decide(db, user, rec, body.decision, body.comment, body.owner)
    run_recovery(rec.incident_id, user.tenant_id, user.email)
    db.expire_all()
    return _rec_out(db.get(Recommendation, rec_id))


@router.post("/incidents/{incident_id}/verify")
def verify(incident_id: uuid.UUID, user: User = Depends(require_role("analyst")), db: Session = Depends(get_db)):
    _owned(db, Incident, incident_id, user)
    result = run_recovery(incident_id, user.tenant_id, user.email)
    return {"status": result["incident_status"], "results": result["verification"]}


@router.get("/incidents/{incident_id}/tasks")
def incident_tasks(incident_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _owned(db, Incident, incident_id, user)
    return [_task_out(t) for t in db.scalars(select(Task).where(Task.incident_id == incident_id).order_by(Task.created_at))]


@router.patch("/tasks/{task_id}")
def update_task(task_id: uuid.UUID, body: TaskPatchIn, user: User = Depends(require_role("analyst")), db: Session = Depends(get_db)):
    task = _owned(db, Task, task_id, user)
    changes = body.model_dump(exclude_none=True)
    for key, value in changes.items():
        setattr(task, key, value.strip())
    audit.record(db, user.tenant_id, user.email, "task.updated", "task", task.id, changes)
    db.commit()
    if task.incident_id:
        run_recovery(task.incident_id, user.tenant_id, user.email)
    return _task_out(task)


@router.get("/incidents/{incident_id}/report")
def report(incident_id: uuid.UUID, format: Literal["json", "markdown"] = "json", user: User = Depends(current_user), db: Session = Depends(get_db)):
    incident = _owned(db, Incident, incident_id, user)
    data = report_service.build_report(db, incident)
    if format == "markdown":
        return Response(
            report_service.to_markdown(data), media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="nexus-report-{incident.id}.md"'},
        )
    return data


# ---- Audit ---------------------------------------------------------------------------------------

@router.get("/audit")
def audit_log(limit: int = 200, user: User = Depends(require_role("approver")), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).where(AuditLog.tenant_id == user.tenant_id).order_by(AuditLog.sequence.desc()).limit(min(max(limit, 1), 1000)))
    return {
        "chain": audit.verify_chain(db, user.tenant_id),
        "entries": [
            {"sequence": r.sequence, "actor": r.actor, "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id, "detail": r.detail, "created_at": r.created_at.isoformat(), "hash": r.hash}
            for r in rows
        ],
    }
