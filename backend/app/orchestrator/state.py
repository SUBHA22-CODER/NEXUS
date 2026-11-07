"""The typed state the orchestrator carries through an investigation."""
from typing import Any, TypedDict


class InvestigationState(TypedDict, total=False):
    investigation_id: str
    tenant_id: str
    project_id: str
    user_id: str
    user_email: str
    events: list[dict]
    dependencies: list[dict]
    active_agents: list[str]
    completed_agents: list[str]
    findings: list[dict]
    # Structured outputs later agents and the correlator consume.
    incident_analysis: dict[str, Any]
    communication_items: list[dict]
    supply_assessments: list[dict]
    security_assessments: list[dict]
    finance_assessments: list[dict]
    manufacturing_assessments: list[dict]
    unowned_work: list[dict]
    evidence_refs: list[str]
    hypotheses: list[dict]
    confidence: float
    uncertainties: list[str]
    recommendations: list[dict]
    risk_score: int
    severity: str
    approval_status: str
    execution_results: list[dict]
    verification_results: list[dict]
    sequence: int


class RecoveryState(TypedDict, total=False):
    incident_id: str
    tenant_id: str
    actor: str
    executed: list[str]
    verification: list[dict]
    incident_status: str
