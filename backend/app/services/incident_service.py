"""Classifies technical failures and correlates them over the declared dependency graph. Pure functions."""
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta

_SIGNATURES = [
    ("connection_pool_exhausted", "Database connection pool exhausted", re.compile(r"pool (is )?exhausted|too many connections|pool saturation", re.IGNORECASE)),
    ("upstream_failure", "Upstream dependency failure", re.compile(r"upstream|bad gateway|status=50[23]", re.IGNORECASE)),
    ("timeout", "Timeout", re.compile(r"time(d)?[ -]?out|deadline exceeded", re.IGNORECASE)),
    ("out_of_memory", "Out of memory", re.compile(r"out of memory|\boom\b|oomkilled", re.IGNORECASE)),
    ("disk_full", "Disk full", re.compile(r"no space left|disk full", re.IGNORECASE)),
    ("tls_failure", "TLS or certificate failure", re.compile(r"certificate|tls handshake", re.IGNORECASE)),
    ("server_error", "Server error (5xx)", re.compile(r"status=5\d\d", re.IGNORECASE)),
]
SUSPECT_DEPLOY_WINDOW = timedelta(minutes=30)


def classify(text: str) -> tuple[str, str]:
    for key, label, pattern in _SIGNATURES:
        if pattern.search(text):
            return key, label
    return "unclassified", "Unclassified error"


def _ts(event: dict) -> datetime:
    return datetime.fromisoformat(event["occurred_at"])


def _upstreams(service: str, edges: list[dict]) -> set[str]:
    seen: set[str] = set()
    queue = deque([service])
    while queue:
        for edge in edges:
            if edge["target"] == queue[0] and edge["source"] not in seen:
                seen.add(edge["source"])
                queue.append(edge["source"])
        queue.popleft()
    return seen


def analyze(events: list[dict], dependencies: list[dict]) -> dict:
    services: dict[str, dict] = {}
    deploys: list[dict] = []
    backlog: dict[str, dict] = {}
    staleness: dict[str, dict] = {}

    def svc(name: str) -> dict:
        return services.setdefault(
            name,
            {"service": name, "errors": 0, "warnings": 0, "requests": 0, "failed_requests": 0, "first_error": None,
             "last_error": None, "first_anomaly": None, "first_error_event": None, "first_anomaly_event": None,
             "signatures": defaultdict(int)},
        )

    for ev in sorted(events, key=_ts):
        if ev["event_type"] == "deploy":
            deploys.append(ev)
            continue
        s = svc(ev["entity"])
        attrs = ev["attributes"]
        status = str(attrs.get("status", ""))
        if status.isdigit():
            s["requests"] += 1
            if int(status) >= 500:
                s["failed_requests"] += 1
        if ev["event_type"] == "service_error":
            s["errors"] += 1
            s["first_error"] = s["first_error"] or ev["occurred_at"]
            s["first_error_event"] = s["first_error_event"] or ev
            s["last_error"] = ev["occurred_at"]
            s["signatures"][classify(ev["raw"] or ev["summary"])[0]] += 1
        elif ev["event_type"] == "service_warning":
            s["warnings"] += 1
        if ev["event_type"] in ("service_error", "service_warning"):
            s["first_anomaly"] = s["first_anomaly"] or ev["occurred_at"]
            s["first_anomaly_event"] = s["first_anomaly_event"] or ev
        if attrs.get("sku") and attrs.get("units_pending") is not None:
            try:
                # Latest reading wins: events are sorted by time.
                backlog[attrs["sku"]] = {"units": float(attrs["units_pending"]), "service": ev["entity"], "event": ev}
            except (TypeError, ValueError):
                pass
        if attrs.get("lag_minutes") is not None:
            try:
                staleness[ev["entity"]] = {"lag_minutes": float(attrs["lag_minutes"]), "event": ev}
            except (TypeError, ValueError):
                pass

    failing = [s for s in services.values() if s["errors"] > 0]
    for s in services.values():
        s["signatures"] = dict(s["signatures"])
        s["top_signature"] = max(s["signatures"], key=s["signatures"].get) if s["signatures"] else None
        s["error_rate"] = round(s["failed_requests"] / s["requests"], 3) if s["requests"] else None

    if not failing:
        return {"services": services, "root_cause": None, "impacted": [], "deploys": deploys,
                "backlog": backlog, "staleness": staleness, "failing": []}

    failing_names = {s["service"] for s in failing}
    # The probable root is a failing service with no failing upstream; ties go to the earliest failure.
    candidates = [s for s in failing if not (_upstreams(s["service"], dependencies) & failing_names)] or failing
    root = min(candidates, key=lambda s: s["first_error"])
    earliest = min(failing, key=lambda s: s["first_error"])

    confidence = 0.5
    reasons = [f"{root['service']} has {root['errors']} errors, first at {root['first_error']}"]
    root_is_declared = any(root["service"] in (d["source"], d["target"]) for d in dependencies)
    if root_is_declared and len(failing) > 1:
        confidence += 0.15
        reasons.append("Its dependents failed too, and no failing service sits upstream of it")
    if earliest["service"] == root["service"]:
        confidence += 0.1
        reasons.append("It was the first service to fail")

    suspect = None
    first_error = datetime.fromisoformat(root["first_error"])
    for deploy in deploys:
        gap = first_error - _ts(deploy)
        if deploy["entity"] == root["service"] and timedelta(0) <= gap <= SUSPECT_DEPLOY_WINDOW:
            suspect = {**deploy, "minutes_before_failure": round(gap.total_seconds() / 60, 1)}
    if suspect:
        confidence += 0.15
        reasons.append(f"Errors began {suspect['minutes_before_failure']} minutes after a deploy of {root['service']}")

    signature = root["top_signature"]
    signature_label = next((label for key, label, _ in _SIGNATURES if key == signature), "Unclassified error")

    impacted, seen = [], {root["service"]}
    queue = deque([root["service"]])
    while queue:
        current = queue.popleft()
        for edge in dependencies:
            if edge["source"] == current and edge["target"] not in seen:
                seen.add(edge["target"])
                queue.append(edge["target"])
                node = services.get(edge["target"])
                impacted.append(
                    {"entity": edge["target"], "domain": edge.get("target_domain", "infrastructure"),
                     "via": current, "relation": edge.get("relation", "depends"),
                     "observed": bool(node and (node["errors"] or node["warnings"]))}
                )

    return {
        "services": services,
        "failing": sorted(failing_names),
        "root_cause": {
            "service": root["service"],
            "signature": signature,
            "signature_label": signature_label,
            "confidence": round(min(confidence, 0.95), 2),
            "reasons": reasons,
            "suspect_deploy": suspect,
            "first_error": root["first_error"],
            "last_error": root["last_error"],
            "error_rate": root["error_rate"],
            "errors": root["errors"],
        },
        "impacted": impacted,
        "deploys": deploys,
        "backlog": backlog,
        "staleness": staleness,
    }
