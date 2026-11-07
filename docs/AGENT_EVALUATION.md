# NEXUS — Agent Evaluation

Each agent is evaluated against controlled inputs (valid, invalid, missing, conflicting, malformed, unrelated, injected, ambiguous, repeated, large) using the deterministic engines and the existing test suite, not by checking whether the LLM "sounds right".

## Infrastructure Agent (`orchestrator/agents.py: incident_agent` → `services/incident_service`)

- **Implementation**: parses ingested `infrastructure` events; classifies error signatures; walks the declared dependency graph to find the probable root cause (a failing service with no failing upstream, earliest failure wins); flags impacted downstream services and a suspect deploy within a 30-minute window.
- **Tools**: `log_correlator` (recorded in `AgentRun.tool_calls`).
- **Outputs**: `root_cause` + `service_impact` findings with severity, confidence, and evidence ids.
- **Evidence**: cites the first error event and the suspect deploy.
- **Tests**: `test_root_cause_prefers_upstream_even_if_downstream_logged_first`, `test_healthy_logs_have_no_root_cause`, `test_log_rejects_are_reported_not_dropped`, `test_json_logs_are_supported`, `test_partial_data_still_investigates_and_skips_agents`, `test_failing_agent_is_reported_and_run_continues`.
- **Limitations**: correlation is limited to the supplied dependency CSV; it does not invent edges.

## Communication Agent (`communication_agent` → `services/communication_service`)

- **Implementation**: `rule_based` extraction (decisions, commitments, open actions, supplier delays) via regex; optional `llm` extraction that is re-validated — quotes must appear verbatim in the source, owners must be a meeting participant, delay numbers come from the parser, never the model.
- **Tools**: `transcript_extractor`.
- **Outputs**: typed items with `owner`, `deadline`, `delay_days`, `supplier_id`, `sku`, evidence ids.
- **Evidence**: cites the source utterance and related follow-ups.
- **Tests**: `test_delay_parser`, `test_transcript_extraction_owners_and_deadlines`, `test_follow_up_merges_into_previous_open_action`, `test_llm_extraction_cannot_invent_quotes_numbers_or_owners`, `test_transcript_injection_cannot_create_or_approve_actions`.
- **Limitations**: NLP is keyword/regex based in deterministic mode; deeply idiomatic language falls back to "not extracted" rather than guessing.

## Supply Agent (`supply_agent` → `services/business_service`)

- **Implementation**: deterministic `stockout_risk` (days of cover, coverage gap, units short, risk level) and `compare_suppliers` (rank by shortfall coverage, lost units, cost, reliability; respect capacity/min-order).
- **Tools**: `stockout_calculator`, `supplier_comparison`.
- **Outputs**: `supply_assessments` with `current`/`baseline`/`worst_case` scenarios and evidence.
- **Evidence**: source snapshot + `calculation` evidence carrying the formula.
- **Tests**: `test_blueprint_stockout_example`, `test_no_gap_when_replenishment_is_in_time`, `test_zero_demand_never_stocks_out`, `test_safety_stock_and_committed_units_reduce_cover`, `test_invalid_inputs_are_rejected`, `test_supplier_ranking_prefers_fewer_lost_units_then_cost`, `test_supplier_capacity_limit_is_respected`.
- **Limitations**: assumes constant demand (stated in the UI); stale/zero-demand/negative inputs are handled or rejected safely.

## Execution Agent (`execution_agent`)

- **Implementation**: identifies open tracked tasks with no owner and open meeting actions, merges duplicates (tracker + meeting), and assigns the live deadline.
- **Tools**: `ownership_checker`.
- **Outputs**: `unowned_work` → `missing_owner` findings → `assign_owner` recommendations.
- **Tests**: `test_owner_is_required_for_assignment`, `test_demo_scenario_connects_all_four_domains`.
- **Limitations**: matching a meeting mention to a service is by service-name pattern; un-matched mentions still surface as unowned work keyed by text.

## Orchestration (LangGraph) verification

- **Nodes**: `triage → incident → communication → supply → execution → correlate → plan → policy → finalize`. A second graph runs recovery: `execute → verify → update_status`.
- **Routing**: `next_step` moves through `active_agents` (agents without data are recorded as `skipped`), then `correlate`.
- **State**: persisted to the `Incident.state` JSON column between graphs, so recovery can run hours later without a live process.
- **Failure handling**: a throwing agent records a failed `AgentRun`, appends an uncertainty, and the run continues (`test_failing_agent_is_reported_and_run_continues`); a whole-run failure sets `failed` + error; a restart marks in-flight runs failed (`test_restart_fails_interrupted_investigations_and_unblocks_the_project`).
- **Bounded execution**: `recursion_limit=40`; LLM `max_retries=1` + 30 s timeout; no unbounded retry.
- **Idempotency**: single decision per recommendation (DB unique constraint + `UPDATE ... WHERE status='proposed'`).

## Evaluation metrics

| Metric | Result |
|---|---|
| Calculation correctness | 100% (all deterministic unit tests pass) |
| Evidence coverage | Every finding in the demo scenario has ≥1 stored evidence id (`test_every_finding_traces_to_stored_evidence`) |
| False positive rate | 0 observed on unrelated-event and injection cases |
| Failure rate | 0 in the 61-test suite |
| Execution latency | 198 ms full deterministic investigation (46 events) |
| Output schema validity | Pydantic-validated (`Finding`, `Hypothesis`); LLM outputs re-validated |
