"""Cross-domain correlation and action planning. Deterministic, so the same inputs always give the same plan."""
from ..schemas import Hypothesis
from ..services import evidence_service

SEVERITY_BANDS = [(70, "critical"), (45, "high"), (20, "warning"), (0, "info")]


def _days(n: float) -> str:
    return f"{n:g} day" + ("" if n == 1 else "s")


def edge_confidence(documented: bool, evidence_both_ends: bool, ordered_in_time: bool) -> float:
    score = 0.2 + 0.3 * documented + 0.2 * evidence_both_ends + 0.25 * ordered_in_time
    return round(min(score, 0.95), 2)


def correlate(state: dict) -> dict:
    analysis = state.get("incident_analysis") or {}
    root = analysis.get("root_cause")
    services = analysis.get("services", {})
    hypotheses: list[Hypothesis] = []
    cite = lambda ev, claim: evidence_service.from_event(state["tenant_id"], state["investigation_id"], ev, claim)
    assessments = state.get("supply_assessments", [])
    at_risk = {a["sku"]: a for a in assessments if a["current"]["risk_level"] != "low" or a["worst_case"]["risk_level"] != "low"}

    if root:
        deploy = root.get("suspect_deploy")
        if deploy:
            version = deploy["attributes"].get("version", "deploy")
            hypotheses.append(
                Hypothesis(
                    source=f"deploy {version}", target=root["service"], source_domain="infrastructure", target_domain="infrastructure",
                    relation="preceded failure of",
                    explanation=f"Errors began {deploy['minutes_before_failure']} minutes after this deploy. The timing suggests a cause but does not prove it.",
                    status="inferred", confidence=root["confidence"], evidence_ids=[cite(deploy, "Deploy shortly before the failure")],
                )
            )
        for item in analysis.get("impacted", []):
            source, target = services.get(item["via"]), services.get(item["entity"])
            if item["domain"] == "infrastructure":
                ends = bool(source and target and source["first_anomaly_event"] and target["first_anomaly_event"])
                ordered = ends and source["first_anomaly"] <= target["first_anomaly"]
                evidence = [cite(source["first_anomaly_event"], f"{item['via']} anomaly"), cite(target["first_anomaly_event"], f"{item['entity']} anomaly")] if ends else []
                hypotheses.append(
                    Hypothesis(
                        source=item["via"], target=item["entity"], source_domain="infrastructure", target_domain="infrastructure", relation=item["relation"],
                        explanation=(
                            f"{item['entity']} depends on {item['via']} and began failing after it."
                            if ordered else f"{item['entity']} depends on {item['via']}, but no failure sequence was seen in the logs."
                        ),
                        status="observed" if ordered else "inferred", confidence=edge_confidence(True, ends, ordered), evidence_ids=evidence,
                    )
                )
            elif item["entity"] in at_risk:
                stale = analysis.get("staleness", {}).get(item["via"])
                hypotheses.append(
                    Hypothesis(
                        source=item["via"], target=item["entity"], source_domain="infrastructure", target_domain="supply", relation=item["relation"],
                        explanation=(
                            f"Inventory sync was {stale['lag_minutes']:g} minutes behind, so the on-hand figure for {item['entity']} may be out of date."
                            if stale else f"{item['entity']} counts come from {item['via']}, which is downstream of the failure."
                        ),
                        status="observed" if stale else "inferred", confidence=edge_confidence(True, bool(stale), bool(stale)),
                        evidence_ids=[cite(stale["event"], "Inventory sync lag")] if stale else [],
                    )
                )
        for sku, held in analysis.get("backlog", {}).items():
            if sku in at_risk:
                hypotheses.append(
                    Hypothesis(
                        source=held["service"], target=sku, source_domain="infrastructure", target_domain="supply", relation="holding orders against",
                        explanation=f"{held['units']:g} units of orders are stuck behind the outage. Recovering payments releases them against the remaining stock.",
                        status="observed", confidence=0.8, evidence_ids=[cite(held["event"], "Order backlog reading")],
                    )
                )

    for a in at_risk.values():
        if a.get("delay"):
            supplier = a["delay"].get("supplier_id") or a["supplier_id"]
            hypotheses.append(
                Hypothesis(
                    source=str(supplier), target=a["sku"], source_domain="communication", target_domain="supply", relation=f"delayed {_days(a['delay_days'])}",
                    explanation=f"Reported in the meeting. It takes the coverage gap from {a['baseline']['coverage_gap_days']} to {a['current']['coverage_gap_days']} days.",
                    status="observed", confidence=0.8, evidence_ids=a["delay"].get("evidence_ids", []),
                )
            )
        hypotheses.append(
            Hypothesis(
                source=a["sku"], target=f"Revenue at risk: {a['sku']}", source_domain="supply", target_domain="supply", relation="exposes",
                explanation=f"{a['current']['units_short']} units short at {a['unit_price']:g} each.",
                status="observed", confidence=0.9, evidence_ids=a["evidence_ids"][:2],
            )
        )
        if a["alternatives"]:
            best = a["alternatives"][0]
            hypotheses.append(
                Hypothesis(
                    source=best["supplier_id"], target=a["sku"], source_domain="supply", target_domain="supply", relation=f"alternative in {_days(best['lead_time_days'])}",
                    explanation=f"{best['name']} is the best-ranked alternative, at an estimated {best['estimated_cost']:,.2f}.",
                    status="inferred", confidence=0.75, evidence_ids=a["evidence_ids"][:1],
                )
            )

    for work in state.get("unowned_work", []):
        if work["service"]:
            hypotheses.append(
                Hypothesis(
                    source=work["service"], target=f"Task: {work['title'][:60]}", source_domain="infrastructure", target_domain="execution", relation="recovery has no owner",
                    explanation="Recovery work for this service exists but nobody is assigned to it.",
                    status="observed", confidence=0.85, evidence_ids=work["evidence_ids"],
                )
            )

    cross_domain = sum(1 for h in hypotheses if h.source_domain != h.target_domain)
    score = 0
    if root:
        score += 40 if root["errors"] >= 5 else 25
    worst_supply = max((1 if a["worst_case"]["risk_level"] == "high" else 2 if a["worst_case"]["risk_level"] == "critical" else 0) for a in assessments) if assessments else 0
    score += {0: 0, 1: 20, 2: 30}[worst_supply]
    score += min(cross_domain * 3, 15) + min(len(state.get("unowned_work", [])) * 5, 15)
    severity = next(label for floor, label in SEVERITY_BANDS if score >= floor)
    overall = round(sum(h.confidence for h in hypotheses) / len(hypotheses), 2) if hypotheses else 0.5
    return {
        "hypotheses": [h.model_dump() for h in hypotheses],
        "risk_score": min(score, 100),
        "severity": severity,
        "confidence": overall,
    }


def plan(state: dict) -> list[dict]:
    """Builds recommendations from fixed templates. Free text from inputs can only reach titles, never action types."""
    recs: list[dict] = []
    analysis = state.get("incident_analysis") or {}
    root = analysis.get("root_cause")
    if root:
        root_evidence = next((f["evidence_ids"] for f in state.get("findings", []) if f["kind"] == "root_cause"), [])
        deploy = root.get("suspect_deploy")
        previous = deploy["attributes"].get("previous_version") if deploy else None
        if previous:
            recs.append({
                "action_type": "service_rollback", "domain": "infrastructure", "priority": 1, "confidence": root["confidence"],
                "title": f"Roll back {root['service']} to {previous}",
                "rationale": f"{root['signature_label']} began {deploy['minutes_before_failure']} minutes after {deploy['attributes'].get('version')} went out. Everything downstream recovers only after this does.",
                "params": {"service": root["service"], "target_version": previous}, "evidence_ids": root_evidence,
            })
        else:
            recs.append({
                "action_type": "create_task", "domain": "infrastructure", "priority": 1, "confidence": root["confidence"],
                "title": f"Investigate {root['service']}: {root['signature_label'].lower()}",
                "rationale": "No recent deploy explains the failure, so engineers need to diagnose it directly.",
                "params": {"service": root["service"], "task_title": f"Investigate {root['service']} failure"}, "evidence_ids": root_evidence,
            })

    for work in state.get("unowned_work", []):
        recs.append({
            "action_type": "assign_owner", "domain": "execution", "priority": 2, "confidence": 0.9,
            "title": f"Assign an owner: {work['title'][:200]}",
            "rationale": "Nobody is responsible for this work." + (f" It is due {work['deadline']}." if work["deadline"] else "") + " A person has to choose the owner.",
            "params": {"task_title": work["title"][:280], "deadline": work["deadline"], "service": work["service"], "task_id": work["task_id"], "needs_owner": True},
            "evidence_ids": work["evidence_ids"],
        })

    for a in state.get("supply_assessments", []):
        if a["current"]["risk_level"] == "low" and a["worst_case"]["risk_level"] == "low":
            continue
        viable = [alt for alt in a["alternatives"] if alt["covers_shortfall"] or alt["units_lost_before_arrival"] == 0]
        if viable:
            best = viable[0]
            others = "; ".join(f"{o['name']}: {o['estimated_cost']:,.2f}, {o['units_lost_before_arrival']} units lost first" for o in a["alternatives"][1:]) or "no other alternatives"
            recs.append({
                "action_type": "expedite_supplier", "domain": "supply", "priority": 3, "confidence": 0.75,
                "title": f"Order {best['order_units']} units of {a['sku']} from {best['name']}",
                "rationale": f"Arrives in {_days(best['lead_time_days'])} for an estimated {best['estimated_cost']:,.2f}, against {a['revenue_at_risk_worst']:,.2f} of revenue at risk. Compared with: {others}.",
                "params": {"sku": a["sku"], "supplier_id": best["supplier_id"], "supplier_name": best["name"], "order_units": best["order_units"], "estimated_cost": best["estimated_cost"], "lead_time_days": best["lead_time_days"]},
                "evidence_ids": a["evidence_ids"],
            })
        else:
            recs.append({
                "action_type": "create_task", "domain": "supply", "priority": 3, "confidence": 0.7,
                "title": f"Find an alternative supplier for {a['sku']}",
                "rationale": f"No supplied alternative covers the {a['worst_case']['units_short']}-unit shortfall.",
                "params": {"sku": a["sku"], "task_title": f"Find an alternative supplier for {a['sku']}"}, "evidence_ids": a["evidence_ids"],
            })
        recs.append({
            "action_type": "notify_stakeholders", "domain": "supply", "priority": 4, "confidence": 0.85,
            "title": f"Alert operations: {a['sku']} is at {a['current']['risk_level']} stockout risk",
            "rationale": f"About {a['current']['days_of_cover']} days of cover, or {a['worst_case']['days_of_cover']} once held orders are released.",
            "params": {"sku": a["sku"], "audience": "operations"}, "evidence_ids": a["evidence_ids"][:2],
        })

    for item in state.get("communication_items", []):
        if item["type"] == "commitment":
            recs.append({
                "action_type": "create_task", "domain": "communication", "priority": 5, "confidence": 0.8,
                "title": f"Track: {item['text'][:200]}",
                "rationale": f"{item['owner']} made this commitment in the meeting" + (f", due {item['deadline']}." if item.get("deadline") else ", with no deadline given."),
                "params": {"task_title": item["text"][:280], "owner": item["owner"], "deadline": item.get("deadline", "")},
                "evidence_ids": item.get("evidence_ids", []),
            })
    return sorted(recs, key=lambda r: r["priority"])
