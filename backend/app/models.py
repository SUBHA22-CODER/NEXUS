"""The twelve core tables from the blueprint. All ids are UUIDs; all business rows carry tenant_id."""
import uuid
from datetime import datetime

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid, event
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, UTCDateTime, utcnow


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def _tenant() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)


def _created() -> Mapped[datetime]:
    return mapped_column(UTCDateTime, default=utcnow)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = _id()
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = _created()


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))  # admin | approver | analyst | viewer
    password_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = _created()


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = _created()


class OperationalEvent(Base):
    """The common event schema: every input is normalized to this before the orchestrator sees it."""

    __tablename__ = "operational_events"
    __table_args__ = (
        UniqueConstraint("project_id", "dedupe_key", name="uq_event_dedupe"),
        Index("ix_event_project_domain_time", "project_id", "domain", "occurred_at"),
    )
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    domain: Mapped[str] = mapped_column(String(30))  # infrastructure | supply | communication | execution
    event_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(10), default="info")  # info | warning | high | critical
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    entity: Mapped[str] = mapped_column(String(200), default="", index=True)
    summary: Mapped[str] = mapped_column(Text)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    source_file: Mapped[str] = mapped_column(String(300))
    source_locator: Mapped[str] = mapped_column(String(50))  # e.g. "line 14", "row 3"
    raw: Mapped[str] = mapped_column(Text, default="")
    dedupe_key: Mapped[str] = mapped_column(String(64))
    ingested_at: Mapped[datetime] = _created()


class Incident(Base):
    """A grouped operational problem and the investigation that explains it."""

    __tablename__ = "incidents"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300), default="Investigation in progress")
    # running | awaiting_approval | in_recovery | resolved | closed_no_action | failed
    status: Mapped[str] = mapped_column(String(30), default="running", index=True)
    severity: Mapped[str] = mapped_column(String(10), default="info")
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    narrative_method: Mapped[str] = mapped_column(String(20), default="template")
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Dependency(Base):
    __tablename__ = "dependencies"
    __table_args__ = (UniqueConstraint("project_id", "source", "target", name="uq_dependency"),)
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(200))  # upstream: failures flow source -> target
    target: Mapped[str] = mapped_column(String(200))
    relation: Mapped[str] = mapped_column(String(60), default="depends")
    source_domain: Mapped[str] = mapped_column(String(30), default="infrastructure")
    target_domain: Mapped[str] = mapped_column(String(30), default="infrastructure")
    origin: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = _created()


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("operational_events.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(20))  # source | calculation
    domain: Mapped[str] = mapped_column(String(30))
    claim: Mapped[str] = mapped_column(Text, default="")
    excerpt: Mapped[str] = mapped_column(Text)
    source_file: Mapped[str] = mapped_column(String(300), default="")
    source_locator: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = _created()


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    agent: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | completed | failed | skipped
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    method: Mapped[str] = mapped_column(String(20), default="deterministic")
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    rationale: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(30))
    priority: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(10))
    confidence: Mapped[float] = mapped_column(Float)
    required_role: Mapped[str] = mapped_column(String(20))
    # proposed | blocked | rejected | executed | verified | failed
    status: Mapped[str] = mapped_column(String(20), default="proposed", index=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    policy_result: Mapped[dict] = mapped_column(JSON, default=dict)
    execution: Mapped[dict] = mapped_column(JSON, default=dict)
    verification: Mapped[dict] = mapped_column(JSON, default=dict)
    executed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = _created()


class Approval(Base):
    __tablename__ = "approvals"
    # One decision per recommendation, enforced by the database as well as the service.
    __table_args__ = (UniqueConstraint("recommendation_id", name="uq_approval_once"),)
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    recommendation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recommendations.id", ondelete="CASCADE"))
    decided_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(10))  # approved | rejected
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = _created()


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("incidents.id", ondelete="SET NULL"), index=True)
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recommendations.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(300))
    owner: Mapped[str] = mapped_column(String(200), default="")
    deadline: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | in_progress | done
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    """Append-only and hash-chained. See the guards below and services/audit.py."""

    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    sequence: Mapped[int] = mapped_column(Integer)
    actor: Mapped[str] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = _created()
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("tenant_id", "sequence", name="uq_audit_sequence"),)


@event.listens_for(AuditLog, "before_update")
@event.listens_for(AuditLog, "before_delete")
def _audit_is_append_only(mapper, connection, target):
    raise ValueError("audit_logs is append-only")
