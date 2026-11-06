"""Append-only, hash-chained audit trail: changing any stored row breaks verification from that row on."""
import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models import AuditLog

GENESIS = "0" * 64


def _digest(tenant_id, sequence, actor, action, entity_type, entity_id, detail, prev_hash) -> str:
    body = json.dumps(
        [str(tenant_id), sequence, actor, action, entity_type, entity_id, detail, prev_hash],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(body.encode()).hexdigest()


def record(
    db: Session,
    tenant_id: uuid.UUID,
    actor: str,
    action: str,
    entity_type: str,
    entity_id,
    detail: dict | None = None,
) -> None:
    detail = detail or {}
    # The unique (tenant_id, sequence) constraint turns a concurrent write into a retry, not a forked chain.
    for attempt in range(5):
        last = db.scalars(
            select(AuditLog).where(AuditLog.tenant_id == tenant_id).order_by(AuditLog.sequence.desc()).limit(1)
        ).first()
        sequence = (last.sequence + 1) if last else 1
        prev = last.hash if last else GENESIS
        row = AuditLog(
            tenant_id=tenant_id,
            sequence=sequence,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            detail=detail,
            created_at=utcnow(),
            prev_hash=prev,
            hash=_digest(tenant_id, sequence, actor, action, entity_type, str(entity_id), detail, prev),
        )
        try:
            with db.begin_nested():
                db.add(row)
            return
        except IntegrityError:
            if attempt == 4:
                raise


def verify_chain(db: Session, tenant_id: uuid.UUID) -> dict:
    prev = GENESIS
    count = 0
    rows = db.scalars(select(AuditLog).where(AuditLog.tenant_id == tenant_id).order_by(AuditLog.sequence))
    for row in rows:
        expected = _digest(
            row.tenant_id, row.sequence, row.actor, row.action, row.entity_type, row.entity_id, row.detail, prev
        )
        if row.prev_hash != prev or row.hash != expected:
            return {"valid": False, "entries": count, "broken_at_sequence": row.sequence}
        prev = row.hash
        count += 1
    return {"valid": True, "entries": count, "broken_at_sequence": None}
