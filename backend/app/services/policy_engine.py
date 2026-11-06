"""Deterministic action policy. No LLM output reaches this module: action types come from the fixed
catalog below and every approval is re-checked here at decision time."""
from dataclasses import asdict, dataclass, field

from ..config import get_settings

ACTION_CATALOG: dict[str, dict] = {
    # Changes production. Only an admin may approve, and only on well-supported evidence.
    "service_rollback": {"risk": "high", "role": "admin", "min_confidence": 0.6},
    # Spends money. The approver role depends on the amount: see _required_role.
    "expedite_supplier": {"risk": "high", "role": "approver", "min_confidence": 0.5},
    "create_task": {"risk": "low", "role": "approver", "min_confidence": 0.3},
    "assign_owner": {"risk": "low", "role": "approver", "min_confidence": 0.3},
    "notify_stakeholders": {"risk": "low", "role": "approver", "min_confidence": 0.3},
}


@dataclass
class PolicyResult:
    allowed: bool
    required_role: str
    risk_level: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _required_role(action_type: str, params: dict) -> str:
    base = ACTION_CATALOG[action_type]["role"]
    if action_type == "expedite_supplier" and float(params.get("estimated_cost", 0)) > get_settings().po_admin_threshold:
        return "admin"
    return base


def evaluate(action_type: str, params: dict, confidence: float, evidence_ids: list[str]) -> PolicyResult:
    spec = ACTION_CATALOG.get(action_type)
    if spec is None:
        return PolicyResult(False, "admin", "high", [f"'{action_type}' is not in the action catalog"])
    reasons: list[str] = []
    allowed = True
    if not evidence_ids:
        allowed = False
        reasons.append("Blocked: no supporting evidence")
    if confidence < spec["min_confidence"]:
        allowed = False
        reasons.append(f"Blocked: confidence {confidence:.2f} is below the required {spec['min_confidence']:.2f}")
    role = _required_role(action_type, params)
    if allowed:
        reasons.append(f"Allowed with {role} approval ({spec['risk']} risk)")
    if role == "admin" and action_type == "expedite_supplier":
        reasons.append(f"Cost exceeds the {get_settings().po_admin_threshold:,.0f} approver limit")
    return PolicyResult(allowed, role, spec["risk"], reasons)
