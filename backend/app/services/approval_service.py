"""Human decisions, execution of approved actions and outcome verification."""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models import Approval, Incident, OperationalEvent, Recommendation, Task, User
from ..security import has_role
from . import audit, business_service, policy_engine

SIMULATED_NOTE = "No live connector is configured: NEXUS recorded this and created a task. A person must carry it out."


def decide(db: Session, user: User, rec: Recommendation, decision: str, comment: str, owner: str) -> Recommendation:
    if rec.status != "proposed":
        raise HTTPException(status.HTTP_409_CONFLICT, f"This recommendation is already {rec.status}")
    # Re-checked now rather than trusting the plan-time result.
    result = policy_engine.evaluate(rec.action_type, rec.params, rec.confidence, rec.evidence_ids)
    if not has_role(user, result.required_role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"This action needs {result.required_role} approval")
    owner = owner.strip()
    if decision == "approved":
        if not result.allowed:
            raise HTTPException(422, "; ".join(result.reasons))
        if rec.params.get("needs_owner") and not owner:
            raise HTTPException(422, "Choose an owner before approving this action")

    params = {**rec.params, "owner": owner or rec.params.get("owner", "")} if decision == "approved" else rec.params
    # Conditional update: of two simultaneous decisions, only one can win.
    won = db.execute(
        update(Recommendation)
        .where(Recommendation.id == rec.id, Recommendation.status == "proposed")
        .values(status="approved" if decision == "approved" else "rejected", params=params)
    ).rowcount
    if not won:
        raise HTTPException(status.HTTP_409_CONFLICT, "This recommendation was just decided by someone else")
    db.add(Approval(tenant_id=user.tenant_id, recommendation_id=rec.id, decided_by=user.id, decision=decision, comment=comment))
    audit.record(
        db, user.tenant_id, user.email, f"recommendation.{decision}", "recommendation", rec.id,
        {"action_type": rec.action_type, "title": rec.title, "comment": comment, "role": user.role, "owner": owner},
    )
    db.commit()
    db.refresh(rec)
    return rec


def _task_title(rec: Recommendation) -> str:
    return rec.params.get("task_title") or rec.title


def execute_approved(db: Session, incident: Incident, actor: str) -> list[str]:
    executed = []
    rows = db.scalars(select(Recommendation).where(Recommendation.incident_id == incident.id, Recommendation.status == "approved"))
    for rec in rows:
        now = utcnow()
        task = Task(
            tenant_id=rec.tenant_id, project_id=incident.project_id, incident_id=incident.id, recommendation_id=rec.id,
            title=_task_title(rec)[:300], owner=rec.params.get("owner", ""), deadline=rec.params.get("deadline", ""),
        )
        db.add(task)
        db.flush()
        tracking_only = rec.action_type in ("create_task", "assign_owner")
        rec.execution = {
            "connector": "task_tracker" if tracking_only else "simulated",
            "task_id": str(task.id),
            "note": "Task created in NEXUS." if tracking_only else SIMULATED_NOTE,
        }
        rec.status, rec.executed_at = "executed", now
        audit.record(db, rec.tenant_id, actor, "recommendation.executed", "recommendation", rec.id, {"connector": rec.execution["connector"], "task_id": str(task.id)})
        executed.append(str(rec.id))
    db.commit()
    return executed


def _verify_rollback(rec: Recommendation, later: list[OperationalEvent]) -> dict:
    service = rec.params["service"]
    seen = [e for e in later if e.entity == service and e.domain == "infrastructure" and e.event_type != "deploy"]
    if not seen:
        return {"status": "pending", "reason": f"No {service} logs received since the action. Upload newer logs to verify."}
    errors = [e for e in seen if e.event_type == "service_error"]
    if errors:
        return {"status": "failed", "reason": f"{len(errors)} of {len(seen)} new {service} log entries are still errors."}
    return {"status": "verified", "reason": f"{len(seen)} new {service} log entries with no errors."}


def _verify_supply(rec: Recommendation, later: list[OperationalEvent]) -> dict:
    sku = rec.params["sku"]
    snaps = sorted((e for e in later if e.entity == sku and e.event_type == "inventory_snapshot"), key=lambda e: e.occurred_at)
    if not snaps:
        return {"status": "pending", "reason": f"No {sku} stock data received since the action. Upload a newer inventory file to verify."}
    a = snaps[-1].attributes
    if a.get("inbound_eta_days") is None:
        return {"status": "pending", "reason": f"The latest {sku} data has no inbound date."}
    risk = business_service.stockout_risk(a["on_hand"], a["daily_demand"], a["inbound_eta_days"], a.get("safety_stock", 0))
    if risk.coverage_gap_days == 0:
        return {"status": "verified", "reason": f"Recalculated from new data: {risk.days_of_cover} days of cover and no gap. {risk.formula}"}
    return {"status": "failed", "reason": f"Recalculated from new data: a gap of {risk.coverage_gap_days} days remains. {risk.formula}"}


def _verify_task(db: Session, rec: Recommendation) -> dict:
    task = db.get(Task, uuid.UUID(rec.execution["task_id"]))
    if task and task.status == "done":
        return {"status": "verified", "reason": "The task is marked done."}
    return {"status": "pending", "reason": "Waiting for the task to be marked done."}


def verify_executed(db: Session, incident: Incident, actor: str) -> list[dict]:
    """Outcomes are checked against data received after the action, not assumed from having dispatched it."""
    results = []
    recs = db.scalars(select(Recommendation).where(Recommendation.incident_id == incident.id, Recommendation.status.in_(("executed", "failed")), Recommendation.executed_at.is_not(None))).all()
    for rec in recs:
        later = db.scalars(
            select(OperationalEvent).where(OperationalEvent.project_id == incident.project_id, OperationalEvent.ingested_at > rec.executed_at)
        ).all()
        if rec.action_type == "service_rollback":
            outcome = _verify_rollback(rec, later)
        elif rec.action_type == "expedite_supplier":
            outcome = _verify_supply(rec, later)
        elif rec.action_type == "notify_stakeholders":
            outcome = {"status": "not_applicable", "reason": "A notification has no measurable outcome."}
        else:
            outcome = _verify_task(db, rec)
        outcome["checked_at"] = utcnow().isoformat()
        changed = rec.verification.get("status") != outcome["status"]
        rec.verification = outcome
        if outcome["status"] == "verified":
            rec.status = "verified"
        elif outcome["status"] == "failed":
            rec.status = "failed"
        elif rec.status == "failed":
            rec.status = "executed"
        if changed:
            audit.record(db, rec.tenant_id, actor, f"verification.{outcome['status']}", "recommendation", rec.id, {"reason": outcome["reason"]})
        results.append({"recommendation_id": str(rec.id), **outcome})
    db.commit()
    return results


def refresh_incident_status(db: Session, incident: Incident) -> str:
    recs = db.scalars(select(Recommendation).where(Recommendation.incident_id == incident.id)).all()
    statuses = [r.status for r in recs]
    if not recs:
        new = "closed_no_action"
    elif "proposed" in statuses or "blocked" in statuses:
        new = "in_recovery" if any(s in ("executed", "verified", "failed", "approved") for s in statuses) else "awaiting_approval"
    elif all(r.status in ("verified", "rejected") or (r.status == "executed" and r.verification.get("status") == "not_applicable") for r in recs):
        new = "resolved" if any(r.status != "rejected" for r in recs) else "closed_no_action"
    else:
        new = "in_recovery"
    if new != incident.status:
        audit.record(db, incident.tenant_id, "system", "incident.status_changed", "incident", incident.id, {"from": incident.status, "to": new})
        incident.status = new
    db.commit()
    return new
