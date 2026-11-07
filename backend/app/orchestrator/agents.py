"""The four specialist agents. Each one calls deterministic tools and returns structured findings;
none of them chooses the next step or can trigger an action."""
import re
import time
import traceback
import uuid
from collections.abc import Callable
from functools import wraps
from typing import Any

from ..db import session_scope, utcnow
from ..models import AgentRun
from ..schemas import Finding
from ..services import business_service, communication_service, evidence_service, finance_service, incident_service, manufacturing_service, security_service
from .state import InvestigationState


class ToolBelt:
    """Runs a tool and records the call, so the Agent Workspace shows what actually happened."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def call(self, name: str, inputs: dict, fn: Callable[[], Any], summarize: Callable[[Any], str] = lambda _: "ok") -> Any:
        started = time.perf_counter()
        try:
            result = fn()
        except Exception as exc:
            self.calls.append({"tool": name, "inputs": inputs, "status": "failed", "output": type(exc).__name__, "duration_ms": round((time.perf_counter() - started) * 1000, 1)})
            raise
        self.calls.append({"tool": name, "inputs": inputs, "status": "ok", "output": summarize(result), "duration_ms": round((time.perf_counter() - started) * 1000, 1)})
        return result


def agent_node(name: str):
    """Records the AgentRun. A failed agent is reported as a gap in the result and does not end the run."""

    def decorate(fn):
        @wraps(fn)
        def node(state: InvestigationState) -> dict:
            sequence = state.get("sequence", 0) + 1
            with session_scope() as db:
                run = AgentRun(tenant_id=uuid.UUID(state["tenant_id"]), incident_id=uuid.UUID(state["investigation_id"]), agent=name, status="running", sequence=sequence)
                db.add(run)
                db.flush()
                run_id = run.id
            tools = ToolBelt()
            completed = [*state.get("completed_agents", []), name]
            try:
                update, findings, note, method = fn(state, tools)
            except Exception as exc:
                traceback.print_exc()
                with session_scope() as db:
                    run = db.get(AgentRun, run_id)
                    run.status, run.error, run.tool_calls, run.finished_at = "failed", f"{type(exc).__name__}: {exc}"[:500], tools.calls, utcnow()
                return {
                    "completed_agents": completed,
                    "sequence": sequence,
                    "uncertainties": [*state.get("uncertainties", []), f"The {name} agent failed, so this assessment is incomplete."],
                }
            with session_scope() as db:
                run = db.get(AgentRun, run_id)
                run.status, run.tool_calls, run.note, run.method, run.finished_at = "completed", tools.calls, note, method, utcnow()
                run.findings = [f.model_dump() for f in findings]
            return {
                **update,
                "completed_agents": completed,
                "sequence": sequence,
                "findings": [*state.get("findings", []), *[f.model_dump() for f in findings]],
                "evidence_refs": [*state.get("evidence_refs", []), *[e for f in findings for e in f.evidence_ids]],
            }

        return node

    return decorate


def _cite(state: InvestigationState, event: dict, claim: str) -> str:
    return evidence_service.from_event(state["tenant_id"], state["investigation_id"], event, claim)


def _events(state: InvestigationState, domain: str) -> list[dict]:
    return [e for e in state["events"] if e["domain"] == domain]


def _hhmm(iso: str) -> str:
    return iso[11:16] if iso else "?"


@agent_node("incident")
def incident_agent(state: InvestigationState, tools: ToolBelt):
    events = _events(state, "infrastructure")
    deps = state.get("dependencies", [])
    analysis = tools.call(
        "log_correlator",
        {"events": len(events), "dependency_edges": len(deps)},
        lambda: incident_service.analyze(events, deps),
        lambda r: f"{len(r['failing'])} failing services",
    )
    findings: list[Finding] = []
    root = analysis["root_cause"]
    if root is None:
        return {"incident_analysis": analysis}, findings, "No service errors in the supplied logs.", "deterministic"

    root_svc = analysis["services"][root["service"]]
    evidence = [_cite(state, root_svc["first_error_event"], f"First {root['service']} error")]
    deploy = root["suspect_deploy"]
    if deploy:
        evidence.append(_cite(state, deploy, f"Deploy of {root['service']} just before the failure"))
    rate = f"{root['error_rate'] * 100:.0f}% of logged requests failed. " if root["error_rate"] is not None else ""
    cause = f" Most likely trigger: {deploy['summary']}." if deploy else ""
    findings.append(
        Finding(
            agent="incident", domain="infrastructure", kind="root_cause",
            title=f"{root['service']}: {root['signature_label'].lower()}",
            detail=f"{root['errors']} errors between {_hhmm(root['first_error'])} and {_hhmm(root['last_error'])} UTC. {rate}{'; '.join(root['reasons'])}.{cause}",
            severity="critical" if root["errors"] >= 5 else "high",
            confidence=root["confidence"], data={"service": root["service"], "signature": root["signature"], "error_rate": root["error_rate"]},
            evidence_ids=evidence,
        )
    )
    for item in analysis["impacted"]:
        node = analysis["services"].get(item["entity"])
        if not node or not item["observed"]:
            continue
        first = node["first_anomaly_event"]
        findings.append(
            Finding(
                agent="incident", domain="infrastructure", kind="service_impact",
                title=f"{item['entity']} affected through {item['via']}",
                detail=f"{node['errors']} errors and {node['warnings']} warnings, first at {_hhmm(node['first_anomaly'])} UTC, after {item['via']} began failing.",
                severity="high" if node["errors"] else "warning", confidence=0.85, data={"service": item["entity"]},
                evidence_ids=[_cite(state, first, f"First anomaly in {item['entity']}")],
            )
        )
    note = f"Probable root cause {root['service']} at {root['confidence']:.2f} confidence, from log signatures and the dependency graph."
    return {"incident_analysis": analysis}, findings, note, "deterministic"


def _known_suppliers(state: InvestigationState) -> dict[str, str]:
    return {e["attributes"]["supplier_id"]: e["attributes"]["name"] for e in _events(state, "supply") if e["event_type"] == "supplier_option"}


@agent_node("communication")
def communication_agent(state: InvestigationState, tools: ToolBelt):
    utterances = [e for e in _events(state, "communication") if e["event_type"] == "utterance"]
    suppliers = _known_suppliers(state)
    items, method = tools.call(
        "transcript_extractor",
        {"utterances": len(utterances), "known_suppliers": len(suppliers)},
        lambda: communication_service.extract(utterances, suppliers),
        lambda r: f"{len(r[0])} items using {r[1]}",
    )
    by_id = {e["id"]: e for e in utterances}
    findings: list[Finding] = []
    labels = {"supplier_delay": "Supplier delay reported", "decision": "Decision recorded", "commitment": "Commitment made", "open_action": "Action with no owner"}
    for item in items:
        evidence = [_cite(state, by_id[item["event_id"]], labels[item["type"]])]
        evidence += [_cite(state, by_id[r], "Follow-up on the same action") for r in item.get("related_event_ids", []) if r in by_id]
        item["evidence_ids"] = evidence
        owner = f" Owner: {item['owner']}." if item.get("owner") else ""
        deadline = f" Deadline: {item['deadline']}." if item.get("deadline") else ""
        findings.append(
            Finding(
                agent="communication", domain="communication", kind=item["type"], title=labels[item["type"]],
                detail=f"{item['speaker']}: \"{item['text']}\".{owner}{deadline}",
                severity="high" if item["type"] in ("supplier_delay", "open_action") else "info",
                confidence=0.8 if method == "rule_based" else 0.85, method=method,
                data={k: item.get(k) for k in ("owner", "deadline", "delay_days", "supplier_id", "sku")},
                evidence_ids=evidence,
            )
        )
    return {"communication_items": items}, findings, f"Read {len(utterances)} utterances and extracted {len(items)} items.", method


def _latest_snapshots(events: list[dict]) -> list[dict]:
    latest: dict[str, dict] = {}
    for ev in sorted((e for e in events if e["event_type"] == "inventory_snapshot"), key=lambda e: (e["occurred_at"], e["ingested_at"])):
        latest[ev["entity"]] = ev
    return list(latest.values())


@agent_node("supply")
def supply_agent(state: InvestigationState, tools: ToolBelt):
    events = _events(state, "supply")
    delays = [i for i in state.get("communication_items", []) if i["type"] == "supplier_delay"]
    analysis = state.get("incident_analysis") or {}
    backlog = analysis.get("backlog", {})
    staleness = analysis.get("staleness", {})
    options = [e for e in events if e["event_type"] == "supplier_option"]
    assessments, findings, uncertainties = [], [], list(state.get("uncertainties", []))
    method = "deterministic"

    for snap in _latest_snapshots(events):
        a = snap["attributes"]
        sku = a["sku"]
        delay = next((d for d in delays if d.get("sku") == sku or (not d.get("sku") and d.get("supplier_id") and d["supplier_id"] == a["supplier_id"])), None)
        primary = next((o for o in options if o["entity"] == sku and o["attributes"]["supplier_id"] == a["supplier_id"]), None)
        base_days = a["inbound_eta_days"] if a["inbound_eta_days"] is not None else (primary["attributes"]["lead_time_days"] if primary else None)
        if base_days is None:
            uncertainties.append(f"{sku}: no inbound date or supplier lead time, so its stockout risk could not be calculated.")
            continue
        delay_days = delay["delay_days"] if delay else 0.0
        args = {"on_hand": a["on_hand"], "daily_demand": a["daily_demand"], "safety_stock": a["safety_stock"]}
        baseline = business_service.stockout_risk(replenishment_days=base_days, **args)
        current = tools.call(
            "stockout_calculator", {"sku": sku, **args, "replenishment_days": base_days + delay_days},
            lambda: business_service.stockout_risk(replenishment_days=base_days + delay_days, **args),
            lambda r: f"cover {r.days_of_cover} days, gap {r.coverage_gap_days} days",
        )
        held = backlog.get(sku)
        worst = current
        if held:
            worst = tools.call(
                "stockout_calculator", {"sku": sku, **args, "replenishment_days": base_days + delay_days, "committed_units": held["units"]},
                lambda: business_service.stockout_risk(replenishment_days=base_days + delay_days, committed_units=held["units"], **args),
                lambda r: f"with held orders: cover {r.days_of_cover} days, gap {r.coverage_gap_days} days",
            )
        assessment = {
            "sku": sku, "name": a["name"], "supplier_id": a["supplier_id"], "unit_price": a["unit_price"],
            "current": current.to_dict(), "baseline": baseline.to_dict(), "worst_case": worst.to_dict(),
            "delay_days": delay_days, "delay": delay, "held_units": held["units"] if held else 0,
            "revenue_at_risk": round(current.units_short * a["unit_price"], 2),
            "revenue_at_risk_worst": round(worst.units_short * a["unit_price"], 2),
            "alternatives": [], "evidence_ids": [],
        }
        if current.risk_level == "low" and worst.risk_level == "low":
            assessments.append(assessment)
            continue

        evidence = [
            _cite(state, snap, f"Current stock position for {sku}"),
            evidence_service.from_calculation(state["tenant_id"], state["investigation_id"], "supply", f"Stockout calculation for {sku}", current.formula),
        ]
        if worst is not current:
            evidence.append(evidence_service.from_calculation(state["tenant_id"], state["investigation_id"], "supply", f"{sku} including orders held behind the outage", worst.formula))
            evidence.append(_cite(state, held["event"], f"Orders held for {sku}"))
        if delay:
            evidence += delay.get("evidence_ids", [])
        alternatives = [
            {**o["attributes"], "event_id": o["id"]}
            for o in options
            if o["entity"] == sku and o["attributes"]["supplier_id"] != a["supplier_id"]
        ]
        ranked = tools.call(
            "supplier_comparison", {"sku": sku, "alternatives": len(alternatives)},
            lambda: business_service.compare_suppliers(alternatives, worst.days_of_cover or 0, worst.units_short, a["daily_demand"], a["unit_price"]),
            lambda r: f"best: {r[0]['name']}" if r else "no alternatives",
        )
        assessment["alternatives"] = ranked
        assessment["evidence_ids"] = evidence
        assessment["snapshot_event_id"] = snap["id"]
        assessments.append(assessment)

        # This is where the domains combine: the same stock looks safe without the meeting transcript.
        hidden = baseline.risk_level == "low" and current.risk_level != "low"
        context = f" The inventory data alone shows no gap; the {delay_days:g}-day delay reported in the meeting creates it." if hidden else ""
        extra = f" Counting {held['units']:g} units in orders held behind the outage: cover {worst.days_of_cover} days, gap {worst.coverage_gap_days} days." if worst is not current else ""
        findings.append(
            Finding(
                agent="supply", domain="supply", kind="stockout_risk",
                title=f"{a['name']} ({sku}): {current.coverage_gap_days}-day coverage gap",
                detail=f"{a['on_hand']:g} units at {a['daily_demand']:g}/day last {current.days_of_cover} days. Replenishment arrives in {current.replenishment_days:g} days.{context}{extra} Assumes constant demand.",
                severity="critical" if current.risk_level == "critical" else "high",
                confidence=0.9, data={"sku": sku, "days_of_cover": current.days_of_cover, "gap_days": current.coverage_gap_days, "units_short": current.units_short, "revenue_at_risk": assessment["revenue_at_risk"]},
                evidence_ids=evidence,
            )
        )
        sync_lag = next(iter(staleness.values()), None)
        if sync_lag:
            uncertainties.append(f"Stock counts for {sku} may be stale: inventory sync was {sync_lag['lag_minutes']:g} minutes behind at last report.")
        uncertainties.append(f"{sku} figures assume demand stays at {a['daily_demand']:g} per day.")

    note = f"Assessed {len(assessments)} SKUs with the deterministic stockout calculator; {len(findings)} at risk."
    return {"supply_assessments": assessments, "uncertainties": uncertainties}, findings, note, method


_SERVICE_NAME = re.compile(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]+)+\b")


def _service_in(text: str, known: set[str]) -> str:
    return next((m for m in _SERVICE_NAME.findall(text) if m in known), "")


@agent_node("execution")
def execution_agent(state: InvestigationState, tools: ToolBelt):
    known_services = {e["entity"] for e in _events(state, "infrastructure")}
    records = [e for e in _events(state, "execution") if e["event_type"] == "task_record"]
    open_records = [e for e in records if e["attributes"]["status"] != "done"]
    missing = tools.call(
        "ownership_checker", {"tasks": len(records)},
        lambda: [e for e in open_records if not e["attributes"]["owner"]],
        lambda r: f"{len(r)} open tasks with no owner",
    )
    work: dict[str, dict] = {}
    findings: list[Finding] = []
    for ev in missing:
        a = ev["attributes"]
        key = a["service"] or a["title"].lower()
        evidence = [_cite(state, ev, f"Task {a['task_id'] or a['title']} has no owner")]
        work[key] = {"title": a["title"], "service": a["service"], "deadline": a["deadline"], "task_id": a["task_id"], "evidence_ids": evidence}
    for item in state.get("communication_items", []):
        if item["type"] != "open_action":
            continue
        service = _service_in(item["text"], known_services)
        key = service or item["text"].lower()
        entry = work.setdefault(key, {"title": item["text"], "service": service, "deadline": "", "task_id": "", "evidence_ids": []})
        entry["evidence_ids"] = [*entry["evidence_ids"], *item.get("evidence_ids", [])]
        # A deadline stated in the meeting is the live one.
        entry["deadline"] = item.get("deadline") or entry["deadline"]
    for entry in work.values():
        where = "the task tracker and the meeting" if entry["task_id"] and len(entry["evidence_ids"]) > 1 else ("the task tracker" if entry["task_id"] else "the meeting")
        findings.append(
            Finding(
                agent="execution", domain="execution", kind="missing_owner", title=f"No owner: {entry['title']}",
                detail=f"Found in {where}." + (f" Deadline: {entry['deadline']}." if entry["deadline"] else ""),
                severity="high", confidence=0.9, data={"service": entry["service"], "task_id": entry["task_id"]},
                evidence_ids=entry["evidence_ids"],
            )
        )
    note = f"Checked {len(records)} tracked tasks and the meeting's open actions; {len(work)} unowned piece{'' if len(work) == 1 else 's'} of work."
    return {"unowned_work": list(work.values())}, findings, note, "deterministic"


def _domain_agent(name: str, domain: str, analyzer, tool_name: str, assessments_key: str):
    """Factory for the security/finance/manufacturing agents: one deterministic
    analyzer each, producing structured, evidence-backed assessments and findings."""

    @agent_node(name)
    def node(state: InvestigationState, tools: ToolBelt):
        events = _events(state, domain)
        analysis = tools.call(
            tool_name, {"events": len(events)},
            lambda: analyzer(events),
            lambda r: f"{len(r['assessments'])} issue(s)",
        )
        findings: list[Finding] = []
        by_entity: dict[str, dict] = {}
        for e in events:
            by_entity.setdefault(e["entity"], e)
        for a in analysis["assessments"]:
            ev = by_entity.get(a["entity"])
            a["evidence_ids"] = [_cite(state, ev, a["title"])] if ev else []
            findings.append(
                Finding(
                    agent=name, domain=domain, kind=a["kind"], title=a["title"], detail=a["detail"],
                    severity=a["severity"], confidence=0.9, data=a["metrics"], evidence_ids=a["evidence_ids"],
                )
            )
        note = f"Analyzed {len(events)} {domain} events; {len(analysis['assessments'])} issue{'s' if len(analysis['assessments']) != 1 else ''}."
        return {assessments_key: analysis["assessments"]}, findings, note, "deterministic"

    return node


security_agent = _domain_agent("security", "security", security_service.analyze, "security_analyzer", "security_assessments")
finance_agent = _domain_agent("finance", "finance", finance_service.analyze, "finance_analyzer", "finance_assessments")
manufacturing_agent = _domain_agent("manufacturing", "manufacturing", manufacturing_service.analyze, "manufacturing_analyzer", "manufacturing_assessments")
