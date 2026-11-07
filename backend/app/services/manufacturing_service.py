"""Deterministic manufacturing/production analysis. All math is pure Python."""
from collections import defaultdict


def analyze(events: list[dict]) -> dict:
    """Returns {"assessments": [...]}, one per machine: downtime, failure count
    and output-vs-capacity utilization."""
    by_machine: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_machine[e["entity"]].append(e)

    assessments: list[dict] = []
    for machine in sorted(by_machine):
        evs = by_machine[machine]
        downs = [e for e in evs if e["attributes"].get("status") == "down"]
        degraded = [e for e in evs if e["attributes"].get("status") == "degraded"]
        maint = [e for e in evs if e["attributes"].get("status") == "maintenance"]
        downtime = round(sum(float(e["attributes"].get("downtime_minutes") or 0) for e in downs), 1)
        failures = len(downs) + len(degraded)

        outputs = [
            (float(e["attributes"]["output_units"]), float(e["attributes"]["capacity_units"]))
            for e in evs
            if e["attributes"].get("output_units") is not None and e["attributes"].get("capacity_units") is not None
        ]
        utilization = None
        if outputs:
            o, c = outputs[-1]
            utilization = round(o / c, 3) if c else None

        if downs:
            risk, sev = "critical", "critical"
            label = "down"
        elif degraded or maint:
            risk, sev = "high", "high"
            label = "degraded" if degraded else "in maintenance"
        else:
            risk, sev = "low", "info"
            label = "operational"

        assessments.append({
            "kind": "production_health",
            "entity": machine,
            "risk_level": risk,
            "severity": sev,
            "title": f"{machine}: {label}",
            "detail": f"{failures} failure/degraded record(s); {downtime} minutes downtime."
            + (f" Latest output {outputs[-1][0]:g}/{outputs[-1][1]:g} units." if outputs else ""),
            "affected": [machine],
            "metrics": {"downtime_minutes": downtime, "failures": failures, "utilization": utilization},
        })

    return {"assessments": assessments}
