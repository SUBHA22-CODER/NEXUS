"""Shared structured types. Agents return Finding objects; the orchestrator decides what happens next."""
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

Domain = Literal["infrastructure", "supply", "communication", "execution", "security", "finance", "manufacturing"]
Severity = Literal["info", "warning", "high", "critical"]
Role = Literal["admin", "approver", "analyst", "viewer"]
Method = Literal["deterministic", "rule_based", "llm"]


class NormalizedEvent(BaseModel):
    """Common event schema. An outage, a stock level and a meeting decision differ only by type and attributes."""

    domain: Domain
    event_type: str
    severity: Severity = "info"
    occurred_at: str  # ISO 8601
    entity: str = ""
    summary: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    source_file: str
    source_locator: str
    raw: str = ""


class Finding(BaseModel):
    agent: str
    domain: Domain
    kind: str
    title: str
    detail: str
    severity: Severity = "info"
    confidence: float = Field(ge=0, le=1)
    method: Method = "deterministic"
    data: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)


class Hypothesis(BaseModel):
    """A causal link between two entities. `status` separates what was observed from what is inferred."""

    source: str
    target: str
    source_domain: Domain
    target_domain: Domain
    relation: str
    explanation: str
    status: Literal["observed", "inferred"]
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)


class RegisterIn(BaseModel):
    organization: str = Field(min_length=2, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    role: Role


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str = Field(default="", max_length=2000)
    owner: str = Field(default="", max_length=200)


class TaskPatchIn(BaseModel):
    status: Literal["open", "in_progress", "done"] | None = None
    owner: str | None = Field(default=None, max_length=200)
