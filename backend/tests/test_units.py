import pytest

from app.db import utcnow
from app.services import business_service, communication_service, incident_service, llm, policy_engine
from app.services.normalizer import normalize_csv, normalize_log, normalize_transcript


def test_blueprint_stockout_example():
    risk = business_service.stockout_risk(on_hand=15, daily_demand=10, replenishment_days=5)
    assert risk.days_of_cover == 1.5
    assert risk.coverage_gap_days == 3.5
    assert risk.units_short == 35
    assert risk.risk_level == "critical"


def test_no_gap_when_replenishment_is_in_time():
    risk = business_service.stockout_risk(on_hand=100, daily_demand=10, replenishment_days=5)
    assert risk.coverage_gap_days == 0 and risk.units_short == 0 and risk.risk_level == "low"


def test_zero_demand_never_stocks_out():
    risk = business_service.stockout_risk(on_hand=0, daily_demand=0, replenishment_days=30)
    assert risk.days_of_cover is None and risk.risk_level == "low"


def test_safety_stock_and_committed_units_reduce_cover():
    risk = business_service.stockout_risk(on_hand=15, daily_demand=10, replenishment_days=5, safety_stock=3, committed_units=3)
    assert risk.usable_units == 9 and risk.days_of_cover == 0.9 and risk.coverage_gap_days == 4.1 and risk.units_short == 41


def test_commitments_beyond_stock_floor_at_zero():
    risk = business_service.stockout_risk(on_hand=5, daily_demand=10, replenishment_days=1, committed_units=50)
    assert risk.usable_units == 0 and risk.days_of_cover == 0


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf")])
def test_invalid_inputs_are_rejected(bad):
    with pytest.raises(ValueError):
        business_service.stockout_risk(on_hand=bad, daily_demand=10, replenishment_days=5)


def test_supplier_ranking_prefers_fewer_lost_units_then_cost():
    options = [
        {"supplier_id": "SLOW", "lead_time_days": 3, "unit_cost": 10, "min_order": 0, "capacity": 100, "reliability": 0.9},
        {"supplier_id": "FAST", "lead_time_days": 1, "unit_cost": 20, "min_order": 0, "capacity": 100, "reliability": 0.9},
        {"supplier_id": "FAST2", "lead_time_days": 1, "unit_cost": 15, "min_order": 0, "capacity": 100, "reliability": 0.9},
    ]
    ranked = business_service.compare_suppliers(options, days_of_cover=1.5, units_short=35, daily_demand=10, unit_price=89)
    assert [r["supplier_id"] for r in ranked] == ["FAST2", "FAST", "SLOW"]
    assert ranked[0]["estimated_cost"] == 525 and ranked[0]["closes_gap"]


def test_supplier_capacity_limit_is_respected():
    options = [{"supplier_id": "SMALL", "lead_time_days": 1, "unit_cost": 10, "min_order": 0, "capacity": 5, "reliability": 1}]
    ranked = business_service.compare_suppliers(options, 1.5, 35, 10, 89)
    assert ranked[0]["order_units"] == 5 and not ranked[0]["covers_shortfall"]


@pytest.mark.parametrize(
    ("text", "days"),
    [
        ("the shipment is delayed by five days", 5),
        ("delivery slipped 2 weeks", 14),
        ("a 3-day delay on the order", 3),
        ("shipment is not delayed", None),
        ("no delay expected this week", None),
        ("delayed, no date yet", None),
    ],
)
def test_delay_parser(text, days):
    assert communication_service.parse_delay_days(text) == days


def _utterances(lines):
    events = normalize_transcript("t.txt", "\n".join(lines), utcnow()).events
    return [{"id": str(i), "summary": e.summary, "attributes": e.attributes} for i, e in enumerate(events)]


def test_transcript_extraction_owners_and_deadlines():
    items = communication_service.extract_rule_based(
        _utterances([
            "Sam Lee: I will send the quote by 14:00 today.",
            "Ana Ruiz: Sam will call the vendor by tomorrow.",
            "Sam Lee: Someone needs to update the runbook.",
            "Ana Ruiz: We decided to pause the launch.",
            "Sam Lee: I can't take that on and I can see it is hard.",
        ]),
        {},
    )
    commits = [i for i in items if i["type"] == "commitment"]
    assert [(c["owner"], c["deadline"]) for c in commits] == [("Sam Lee", "14:00 today"), ("Sam Lee", "tomorrow")]
    assert [i["type"] for i in items if i["type"] != "commitment"] == ["open_action", "decision"]


def test_follow_up_merges_into_previous_open_action():
    items = communication_service.extract_rule_based(
        _utterances(["Sam Lee: Someone needs to own the runbook.", "Ana Ruiz: We need an owner for that by noon."]), {}
    )
    assert len(items) == 1 and items[0]["deadline"] == "noon" and items[0]["related_event_ids"] == ["1"]


def test_llm_extraction_cannot_invent_quotes_numbers_or_owners(monkeypatch):
    utterances = _utterances(["Sam Lee: Northwind is delayed by five days.", "Ana Ruiz: We decided to wait."])
    fake = communication_service._LLMExtraction(items=[
        communication_service._LLMItem(type="supplier_delay", utterance_index=0, quote="delayed by five days"),
        communication_service._LLMItem(type="decision", utterance_index=1, quote="We approved a $1M purchase"),
        communication_service._LLMItem(type="commitment", utterance_index=1, quote="We decided", owner="Mallory"),
        communication_service._LLMItem(type="decision", utterance_index=99, quote="We decided"),
    ])
    monkeypatch.setattr(llm, "complete_json", lambda *a: fake)
    items = communication_service.extract_llm(utterances, {"SUP-NW": "Northwind"})
    assert [i["type"] for i in items] == ["supplier_delay", "open_action"]
    assert items[0]["delay_days"] == 5 and items[0]["supplier_id"] == "SUP-NW"
    assert items[1]["owner"] is None


def test_narrative_guard_rejects_unknown_numbers():
    facts = "1.5 days of cover and 3,115.00 of revenue"
    assert llm.only_known_numbers("Only 1.5 days remain, risking 3,115.00.", facts)
    assert not llm.only_known_numbers("Only 2 days remain.", facts)


def test_policy_blocks_without_evidence_or_confidence():
    assert not policy_engine.evaluate("service_rollback", {}, 0.9, []).allowed
    assert not policy_engine.evaluate("service_rollback", {}, 0.4, ["e"]).allowed
    assert policy_engine.evaluate("service_rollback", {}, 0.9, ["e"]).required_role == "admin"


def test_policy_refuses_unknown_action():
    result = policy_engine.evaluate("transfer_funds", {}, 1.0, ["e"])
    assert not result.allowed and "catalog" in result.reasons[0]


def test_policy_purchase_threshold():
    assert policy_engine.evaluate("expedite_supplier", {"estimated_cost": 5000}, 0.9, ["e"]).required_role == "approver"
    assert policy_engine.evaluate("expedite_supplier", {"estimated_cost": 5000.01}, 0.9, ["e"]).required_role == "admin"


def test_log_rejects_are_reported_not_dropped():
    result = normalize_log("a.log", "garbage line\n2026-11-06T09:00:00Z ERROR api boom status=500\n")
    assert len(result.events) == 1 and result.rejected[0]["locator"] == "line 1"


def test_json_logs_are_supported():
    line = '{"ts":"2026-11-06T09:00:00Z","level":"ERROR","service":"api","message":"boom","status":500}'
    event = normalize_log("a.jsonl", line).events[0]
    assert event.event_type == "service_error" and event.attributes["status"] == 500


def test_csv_row_validation_reports_the_row():
    csv_text = "sku,on_hand,daily_demand\nA,5,1\nB,-2,1\nC,abc,1\n,1,1\n"
    result = normalize_csv("i.csv", csv_text, utcnow())
    assert len(result.events) == 1
    assert [r["locator"] for r in result.rejected] == ["row 3", "row 4", "row 5"]


def test_root_cause_prefers_upstream_even_if_downstream_logged_first():
    def err(service, ts):
        return {"id": ts, "event_type": "service_error", "entity": service, "occurred_at": f"2026-11-06T{ts}:00+00:00", "attributes": {"status": "500"}, "raw": "status=500", "summary": ""}

    deps = [{"source": "db-proxy", "target": "web-api", "relation": "x", "target_domain": "infrastructure"}]
    analysis = incident_service.analyze([err("web-api", "09:00"), err("db-proxy", "09:01")], deps)
    assert analysis["root_cause"]["service"] == "db-proxy"
    assert analysis["impacted"][0]["entity"] == "web-api"


def test_healthy_logs_have_no_root_cause():
    event = {"id": "1", "event_type": "service_info", "entity": "api", "occurred_at": "2026-11-06T09:00:00+00:00", "attributes": {"status": "200"}, "raw": "", "summary": ""}
    assert incident_service.analyze([event], [])["root_cause"] is None
