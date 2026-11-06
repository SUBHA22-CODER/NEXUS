"""LangGraph state machines: one investigates, one runs recovery after a human decision.

The two are separate because a person may answer hours later. State is stored on the incident row between
them, so nothing depends on a process staying alive. Agents never talk to each other; `route` picks the next.
"""
import logging
import traceback
import uuid
from datetime import UTC, datetime

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from ..db import session_scope, utcnow
from ..models import AgentRun, Dependency, Incident, OperationalEvent, Recommendation
from ..services import approval_service, audit, policy_engine, report_service
from . import agents
from . import correlate as correlation
from .state import InvestigationState, RecoveryState

log = logging.getLogger("nexus.orchestrator")
AGENT_ORDER = ["incident", "communication", "supply", "execution"]


def _json_safe(value):
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return value


def _event_dict(ev: OperationalEvent) -> dict:
    return {
        "id": str(ev.id), "domain": ev.domain, "event_type": ev.event_type, "severity": ev.severity,
        "occurred_at": ev.occurred_at.isoformat(), "ingested_at": ev.ingested_at.isoformat(), "entity": ev.entity,
        "summary": ev.summary, "attributes": ev.attributes, "source_file": ev.source_file,
        "source_locator": ev.source_locator, "raw": ev.raw,
    }


def triage(state: InvestigationState) -> dict:
    """Decides which agents this investigation needs, from the data that is actually present."""
    with session_scope() as db:
        project_id = uuid.UUID(state["project_id"])
        tenant_id = uuid.UUID(state["tenant_id"])
        events = db.scalars(
            select(OperationalEvent).where(OperationalEvent.project_id == project_id, OperationalEvent.tenant_id == tenant_id).order_by(OperationalEvent.occurred_at)
        ).all()
        deps = db.scalars(select(Dependency).where(Dependency.project_id == project_id, Dependency.tenant_id == tenant_id)).all()
        event_dicts = [_event_dict(e) for e in events]
        dep_dicts = [{"source": d.source, "target": d.target, "relation": d.relation, "source_domain": d.source_domain, "target_domain": d.target_domain} for d in deps]
        domains = {e["domain"] for e in event_dicts}
        needed = {
            "incident": "infrastructure" in domains,
            "communication": "communication" in domains,
            "supply": "supply" in domains,
            "execution": "execution" in domains or "communication" in domains,
        }
        active = [a for a in AGENT_ORDER if needed[a]]
        sequence = 0
        for agent in AGENT_ORDER:
            if not needed[agent]:
                sequence += 1
                db.add(AgentRun(tenant_id=tenant_id, incident_id=uuid.UUID(state["investigation_id"]), agent=agent, status="skipped", sequence=sequence, note="No relevant data in this project.", finished_at=utcnow()))
    uncertainties = []
    if not deps:
        uncertainties.append("No dependency map was supplied, so links between services could not be traced.")
    for domain, label in (("infrastructure", "logs"), ("supply", "inventory data"), ("communication", "transcripts")):
        if domain not in domains:
            uncertainties.append(f"No {label} supplied: this view may be missing a domain.")
    return {"events": event_dicts, "dependencies": dep_dicts, "active_agents": active, "completed_agents": [], "findings": [], "evidence_refs": [], "uncertainties": uncertainties, "sequence": sequence}


def next_step(state: InvestigationState) -> str:
    remaining = [a for a in state["active_agents"] if a not in state["completed_agents"]]
    return remaining[0] if remaining else "correlate"


def correlate_node(state: InvestigationState) -> dict:
    return correlation.correlate(state)


def plan_node(state: InvestigationState) -> dict:
    return {"recommendations": correlation.plan(state)}


def policy_node(state: InvestigationState) -> dict:
    """Every recommendation is stored with its policy verdict. Nothing executes here."""
    incident_id, tenant_id = uuid.UUID(state["investigation_id"]), uuid.UUID(state["tenant_id"])
    with session_scope() as db:
        for rec in state.get("recommendations", []):
            verdict = policy_engine.evaluate(rec["action_type"], rec["params"], rec["confidence"], rec["evidence_ids"])
            db.add(
                Recommendation(
                    tenant_id=tenant_id, incident_id=incident_id, action_type=rec["action_type"], title=rec["title"][:300], rationale=rec["rationale"],
                    domain=rec["domain"], priority=rec["priority"], risk_level=verdict.risk_level, confidence=rec["confidence"], required_role=verdict.required_role,
                    status="proposed" if verdict.allowed else "blocked", params=rec["params"], evidence_ids=rec["evidence_ids"], policy_result=verdict.to_dict(),
                )
            )
    return {"approval_status": "pending" if state.get("recommendations") else "none"}


def finalize_node(state: InvestigationState) -> dict:
    incident_id = uuid.UUID(state["investigation_id"])
    title, summary, method = report_service.narrative(state)
    stored = _json_safe({k: v for k, v in state.items() if k != "events"})
    stored["event_count"] = len(state["events"])
    with session_scope() as db:
        incident = db.get(Incident, incident_id)
        incident.title, incident.summary, incident.narrative_method = title[:300], summary, method
        incident.severity, incident.risk_score, incident.state = state.get("severity", "info"), state.get("risk_score", 0), stored
        incident.status = "awaiting_approval" if state.get("recommendations") else "closed_no_action"
        audit.record(
            db, incident.tenant_id, "system", "investigation.completed", "incident", incident.id,
            {"severity": incident.severity, "risk_score": incident.risk_score, "recommendations": len(state.get("recommendations", [])), "narrative_method": method},
        )
    return {}


def build_investigation_graph():
    graph = StateGraph(InvestigationState)
    graph.add_node("triage", triage)
    graph.add_node("incident", agents.incident_agent)
    graph.add_node("communication", agents.communication_agent)
    graph.add_node("supply", agents.supply_agent)
    graph.add_node("execution", agents.execution_agent)
    graph.add_node("correlate", correlate_node)
    graph.add_node("plan", plan_node)
    graph.add_node("policy", policy_node)
    graph.add_node("finalize", finalize_node)
    graph.add_edge(START, "triage")
    routes = {a: a for a in AGENT_ORDER} | {"correlate": "correlate"}
    graph.add_conditional_edges("triage", next_step, routes)
    for agent in AGENT_ORDER:
        graph.add_conditional_edges(agent, next_step, routes)
    graph.add_edge("correlate", "plan")
    graph.add_edge("plan", "policy")
    graph.add_edge("policy", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def _load(state: RecoveryState, db) -> Incident:
    incident = db.get(Incident, uuid.UUID(state["incident_id"]))
    if incident is None or str(incident.tenant_id) != state["tenant_id"]:
        raise ValueError("Incident not found for this tenant")
    return incident


def execute_node(state: RecoveryState) -> dict:
    with session_scope() as db:
        return {"executed": approval_service.execute_approved(db, _load(state, db), state["actor"])}


def verify_node(state: RecoveryState) -> dict:
    with session_scope() as db:
        return {"verification": approval_service.verify_executed(db, _load(state, db), state["actor"])}


def status_node(state: RecoveryState) -> dict:
    with session_scope() as db:
        return {"incident_status": approval_service.refresh_incident_status(db, _load(state, db))}


def build_recovery_graph():
    graph = StateGraph(RecoveryState)
    graph.add_node("execute", execute_node)
    graph.add_node("verify", verify_node)
    graph.add_node("update_status", status_node)
    graph.add_edge(START, "execute")
    graph.add_edge("execute", "verify")
    graph.add_edge("verify", "update_status")
    graph.add_edge("update_status", END)
    return graph.compile()


_investigation = build_investigation_graph()
_recovery = build_recovery_graph()


def run_investigation(incident_id: uuid.UUID) -> None:
    with session_scope() as db:
        incident = db.get(Incident, incident_id)
        initial: InvestigationState = {
            "investigation_id": str(incident.id), "tenant_id": str(incident.tenant_id), "project_id": str(incident.project_id), "user_id": str(incident.created_by),
        }
    try:
        _investigation.invoke(initial, {"recursion_limit": 40})
    except Exception as exc:
        traceback.print_exc()
        log.error("Investigation %s failed: %s", incident_id, exc)
        with session_scope() as db:
            incident = db.get(Incident, incident_id)
            incident.status, incident.error, incident.title = "failed", f"{type(exc).__name__}: {exc}"[:1000], "Investigation failed"
            audit.record(db, incident.tenant_id, "system", "investigation.failed", "incident", incident.id, {"error": type(exc).__name__})


def run_recovery(incident_id: uuid.UUID, tenant_id: uuid.UUID, actor: str) -> dict:
    return _recovery.invoke({"incident_id": str(incident_id), "tenant_id": str(tenant_id), "actor": actor})
