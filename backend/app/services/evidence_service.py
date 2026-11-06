"""Stores source references and calculation records so every finding can be traced back."""
import uuid

from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import Evidence


def _row(db: Session, **fields) -> str:
    evidence = Evidence(**fields)
    db.add(evidence)
    db.flush()
    return str(evidence.id)


def from_event(tenant_id: str, incident_id: str, event: dict, claim: str) -> str:
    with session_scope() as db:
        return _row(
            db,
            tenant_id=uuid.UUID(tenant_id),
            incident_id=uuid.UUID(incident_id),
            event_id=uuid.UUID(event["id"]),
            kind="source",
            domain=event["domain"],
            claim=claim,
            excerpt=event["raw"] or event["summary"],
            source_file=event["source_file"],
            source_locator=event["source_locator"],
        )


def from_calculation(tenant_id: str, incident_id: str, domain: str, claim: str, formula: str) -> str:
    with session_scope() as db:
        return _row(
            db,
            tenant_id=uuid.UUID(tenant_id),
            incident_id=uuid.UUID(incident_id),
            event_id=None,
            kind="calculation",
            domain=domain,
            claim=claim,
            excerpt=formula,
            source_file="business_service",
            source_locator="deterministic",
        )
