"""Deterministic cybersecurity event analysis. No number is produced by an LLM.

Events come from the security normalizer (domain="security"): failed_login,
suspicious_auth, privilege_escalation, vuln_alert. This module groups and
classifies them into evidence-backed risk assessments.
"""
from collections import Counter, defaultdict

_BY_TYPE_DEFAULT_SEVERITY = {
    "failed_login": "warning",
    "suspicious_auth": "high",
    "privilege_escalation": "critical",
    "vuln_alert": "high",
    "brute_force": "critical",
}


def _risk_from_severity(severity: str) -> str:
    return "critical" if severity == "critical" else "high" if severity == "high" else "warning"


def analyze(events: list[dict]) -> dict:
    """Returns {"assessments": [...]}. Each assessment is a self-contained,
    deterministic risk item the agent turns into a Finding and the correlator
    turns into a Hypothesis."""
    assessments: list[dict] = []

    # Group failed logins by the source IP (the event entity).
    failed = [e for e in events if e["event_type"] == "failed_login"]
    by_ip: dict[str, list[dict]] = defaultdict(list)
    for e in failed:
        by_ip[e["entity"]].append(e)

    for ip in sorted(by_ip, key=lambda k: -len(by_ip[k])):
        evs = by_ip[ip]
        n = len(evs)
        if n < 3:
            continue
        kind = "brute_force" if n >= 5 else "suspicious_auth"
        sev = "critical" if n >= 5 else "high"
        users = [u for u, _ in Counter(e["attributes"].get("user", "") for e in evs).most_common() if u]
        assessments.append({
            "kind": kind,
            "entity": ip,
            "risk_level": sev,
            "severity": sev,
            "title": f"{n} failed logins from {ip}",
            "detail": f"{n} failed authentication attempts from {ip}"
            + (f" against {', '.join(users)}" if users else "")
            + (". Consistent with credential brute-forcing." if n >= 5 else "."),
            "affected": [ip, *users],
            "metrics": {"failed_attempts": n, "distinct_users": len(users)},
        })

    for e in events:
        et = e["event_type"]
        if et == "privilege_escalation":
            sev = _BY_TYPE_DEFAULT_SEVERITY.get(et, "critical")
            assessments.append({
                "kind": "privilege_escalation", "entity": e["entity"], "risk_level": "critical", "severity": "critical",
                "title": f"Privilege escalation on {e['entity']}",
                "detail": e["summary"],
                "affected": [e["entity"]],
                "metrics": {"source_ip": e["attributes"].get("source_ip", "")},
            })
        elif et == "vuln_alert":
            sev = e["attributes"].get("severity") or _BY_TYPE_DEFAULT_SEVERITY["vuln_alert"]
            assessments.append({
                "kind": "vuln_alert", "entity": e["entity"],
                "risk_level": _risk_from_severity(sev), "severity": sev,
                "title": f"Vulnerability on {e['entity']}",
                "detail": e["summary"],
                "affected": [e["entity"]],
                "metrics": {"cve": e["attributes"].get("cve", "")},
            })
        elif et == "suspicious_auth" and e["entity"] not in by_ip:
            sev = _BY_TYPE_DEFAULT_SEVERITY["suspicious_auth"]
            assessments.append({
                "kind": "suspicious_auth", "entity": e["entity"], "risk_level": "high", "severity": sev,
                "title": f"Suspicious authentication from {e['entity']}",
                "detail": e["summary"], "affected": [e["entity"]],
                "metrics": {"source_ip": e["attributes"].get("source_ip", "")},
            })

    return {"assessments": assessments}
