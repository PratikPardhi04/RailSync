"""RailSync AI - LangGraph orchestrated agentic planning workflow.

This replaces the former sequential function-chain engine. The graph is:

  validate -> (parallel) maintenance/traffic/priority -> merge -> historical ->
  rag -> web_research(Tavily, evidence only) -> evidence_validation ->
  candidate(LLM) -> cp_sat(deterministic) -> simulate(deterministic) ->
  routing(LLM proposes) -> route_opt(deterministic) -> hard-conflict gate(loop) ->
  constraint validator(loop) -> risk -> decision fusion(advisory) -> report ->
  PENDING_REVIEW

Architecture rules enforced here:
  * LLMs propose/interpret; deterministic engines decide (CP-SAT, simulator,
    route optimizer, validator, hard-conflict gate).
  * Officers never have to approve an unsafe plan - the AI auto-replans
    internally on hard conflicts, bounded by max_retries.
  * Decision Fusion is advisory (RECOMMEND_APPROVE / RECOMMEND_REVIEW) and can
    never change the CP-SAT result.
"""
import os
import sys
import time
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

_BACKEND_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _BACKEND_SRC not in sys.path:
    sys.path.insert(0, _BACKEND_SRC)

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents import (
    maintenance_agent, traffic_agent, priority_agent, historical_agent,
    candidate_generator, constraint_validator, risk_agent,
    decision_fusion_agent, routing_agent, web_research_agent,
)
from app.optimization import cp_sat_optimizer, route_optimizer
from app.simulation import simulator
from app.rag.knowledge_base import knowledge_base
from app.schemas.workflow import (
    WorkflowState, state_from_dict,
    ReplanningConstraint,
    hours_minutes_to_mins, to_time_str,
    WebSearchEvidence,
)
from app.services.constraints import (
    structured_constraints_from_feedback, parse_avoid_window,
)
from app.services.tavily_client import validate_evidence

MAX_RETRIES = int(os.getenv("RAILS_MAX_RETRIES", "3"))
PREMIUM_TYPES = ("RAJDHANI", "SHATABDI", "VANDE_BHARAT")
HARD_PREMIUM_DELAY_MIN = 10

# Emitters are callables and cannot live inside the Pydantic graph state, so
# they are kept in a registry keyed by a serializable run_id (one entry per
# run_workflow invocation; cleaned up on completion).
_EMITTERS: Dict[str, Any] = {}


def _emit_for(state: WorkflowState):
    return _EMITTERS.get(state.run_id)


def _S(state) -> WorkflowState:
    """LangGraph invokes nodes with the raw channel dict; normalize to model."""
    return state if isinstance(state, WorkflowState) else WorkflowState(**state)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _d(value: Any) -> Any:
    """Model -> dict (JSON-safe) for results/reports."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {k: _d(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_d(v) for v in value]
    return value


def _to_minutes(time_str: str) -> int:
    return hours_minutes_to_mins(time_str)


def _window_str(start_min: int, end_min: int) -> str:
    return f"{to_time_str(start_min)}-{to_time_str(end_min)}"


def _record_step(state: WorkflowState, name: str, status: str, data: Optional[dict],
                 event: Optional[str], emit_event=None, *, prior: Optional[List[dict]] = None) -> List[dict]:
    entry = {
        "agent": name,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "data": dict(data or {}, workflow_event=event),
    }
    base = prior if prior is not None else list(state.steps)
    steps = base + [entry]
    emit_event = emit_event or _emit_for(state)
    if emit_event:
        try:
            emit_event("agent_progress", {
                "request_id": state.request_id,
                "step": name,
                "status": status,
                "version": state.plan_version,
                "data": entry["data"],
            })
        except Exception:
            pass
    return steps


def _merge_avoid_feedback(officer_feedback: Optional[Dict], hard_avoid: List) -> Optional[Dict]:
    if not officer_feedback and not hard_avoid:
        return None
    merged = dict(officer_feedback or {})
    windows = list(hard_avoid)
    of_avoid = (officer_feedback or {}).get("avoid_time", "")
    if of_avoid:
        for s, e in parse_avoid_window(of_avoid):
            windows.append((s, e))
    if windows:
        merged["avoid_time"] = ",".join(_window_str(s, e) for s, e in sorted(windows))
    return merged


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def node_validate(state: WorkflowState) -> dict:
    state = _S(state)
    req = state.request
    required = ["department", "maintenance_type", "location", "section",
                "requested_date", "duration_minutes", "priority"]
    errors = [f"Missing required field: {f}" for f in required if not req.get(f)]
    duration = int(req.get("duration_minutes") or 0)
    if duration < 30:
        errors.append("Minimum maintenance duration is 30 minutes")
    if duration > 480:
        errors.append("Maximum maintenance duration is 480 minutes")

    steps = _record_step(state, "request_received", "completed",
                         {"request_id": state.request_id}, "workflow_started", None)
    if errors:
        steps = _record_step(state, "data_validation", "failed", {"valid": False, "errors": errors},
                             "validation_completed", None, prior=steps)
        return {"workflow_status": "FAILED", "errors": errors, "steps": steps}
    steps = _record_step(state, "data_validation", "completed", {"valid": True},
                         "validation_completed", None, prior=steps)
    # Parallel fan-out agents are recorded by node_merge (single writer) so
    # step entries survive the Send fan-out deterministically.
    return {"workflow_status": "RUNNING", "steps": steps}


def _branch_validate(state: WorkflowState) -> List[Send]:
    state = _S(state)
    """Parallel fan-out after validation (LangGraph dynamic fan-out)."""
    base = {
        "request_id": state.request_id,
        "plan_version": state.plan_version,
        "request": state.request,
        "trains": state.trains,
        "officer_feedback": state.officer_feedback,
        "max_retries": state.max_retries,
        "start_time": state.start_time,
        "run_id": state.run_id,
        "steps": list(state.steps),
    }
    return [
        Send("maintenance", base),
        Send("traffic", base),
        Send("priority", base),
    ]


def _emit_completed(state: WorkflowState, agent: str):
    emit = _emit_for(state)
    if emit:
        try:
            emit("agent_completed", {"agent": agent, "request_id": state.request_id})
        except Exception:
            pass


def node_maintenance(state: WorkflowState) -> dict:
    state = _S(state)
    # Parallel branch: only writes its own channel. Steps for fan-out are
    # written by validate (in_progress) and merge (completed) to avoid
    # last-write-wins clobbering across concurrent branches.
    result = maintenance_agent.run(state.request)
    _emit_completed(state, "maintenance_agent")
    return {"maintenance_analysis": result}


def node_traffic(state: WorkflowState) -> dict:
    state = _S(state)
    result = traffic_agent.run(state.request, state.trains)
    _emit_completed(state, "traffic_agent")
    return {"traffic_analysis": result}


def node_priority(state: WorkflowState) -> dict:
    state = _S(state)
    result = priority_agent.run(state.request, state.trains)
    _emit_completed(state, "priority_agent")
    return {"priority_analysis": result}


def node_merge(state: WorkflowState) -> dict:
    state = _S(state)
    """Join after the parallel analysis phase (single writer for stable steps)."""
    extras = []
    summ = {
        "maintenance_agent": _d(state.maintenance_analysis).get("summary", ""),
        "traffic_agent": f"{_d(state.traffic_analysis).get('total_affected', 0)} trains affected",
        "priority_agent": _d(state.priority_analysis).get("priority_level", "MEDIUM"),
    }
    for agent in ("maintenance_agent", "traffic_agent", "priority_agent"):
        extras.append({"agent": agent, "status": "in_progress",
                       "timestamp": datetime.utcnow().isoformat(),
                       "data": {"workflow_event": "agent_started"}})
        extras.append({"agent": agent, "status": "completed",
                       "timestamp": datetime.utcnow().isoformat(),
                       "data": {"workflow_event": "agent_completed",
                                "summary": summ.get(agent, "")}})
    steps = list(state.steps) + extras
    return {"steps": steps}


def node_historical(state: WorkflowState) -> dict:
    state = _S(state)
    steps = _record_step(state, "historical_agent", "in_progress", None, "agent_started", None)
    result = historical_agent.run(state.request, knowledge_base)
    steps = _record_step(state, "historical_agent", "completed",
                         {"similar_cases": len(_d(result).get("similar_cases", []))},
                         "agent_completed", None, prior=steps)
    return {"historical_analysis": result, "steps": steps}


def node_rag(state: WorkflowState) -> dict:
    state = _S(state)
    steps = _record_step(state, "rag_retrieval", "in_progress", None, "rag_started", None)
    query = f"{state.request.get('maintenance_type', '')} {state.request.get('section', '')}"
    docs = knowledge_base.search(query, k=3)
    evidence = {
        "query": query,
        "documents": [
            {"id": d.get("id", ""), "title": d.get("title", ""), "source": d.get("source", ""),
             "content": d.get("content", ""), "score": d.get("score", 0),
             "source_type": d.get("category", "knowledge")}
            for d in docs
        ],
        "total_retrieved": len(docs),
        "engine": "faiss",
    }
    steps = _record_step(state, "rag_retrieval", "completed",
                         {"documents_retrieved": len(docs)}, "rag_completed", None)
    return {"rag_evidence": evidence, "steps": steps}


def node_web_research(state: WorkflowState) -> dict:
    state = _S(state)
    steps = _record_step(state, "web_research", "in_progress", None, "web_search_started", None)
    result = web_research_agent.run(state.request, _d(state.rag_evidence), state.web_evidence)
    d = _d(result)
    if d.get("status") == "failed":
        steps = _record_step(state, "web_research", "failed",
                             {"error": d.get("error", "Tavily search failed"),
                              "search_count": d.get("search_count", 0)},
                             "web_search_failed", None, prior=steps)
        # fallback: workflow continues on internal RAG/database evidence only
        return {"web_evidence": result, "steps": steps}
    steps = _record_step(state, "web_research", "completed",
                         {"results": d.get("relevant_results", 0),
                          "sources": d.get("total_results", 0),
                          "search_count": d.get("search_count", 0)},
                         "web_search_completed", None, prior=steps)
    return {"web_evidence": result, "steps": steps}


def node_evidence(state: WorkflowState) -> dict:
    state = _S(state)
    steps = _record_step(state, "evidence_validation", "in_progress", None, "evidence_started", None)
    raw = _d(state.web_evidence) or {}
    if raw.get("sources"):
        validated = validate_evidence(raw)
    else:
        validated = dict(raw)
        validated["summary"] = raw.get("summary", "") or (
            "No web sources to validate; continuing with internal RAG/historical evidence.")
    ev = WebSearchEvidence(**{k: v for k, v in validated.items()
                              if k in WebSearchEvidence.model_fields})
    steps = _record_step(state, "evidence_validation", "completed",
                         {"validated": len(ev.sources),
                          "authoritative": sum(1 for s in ev.sources if s.get("authoritative")),
                          "status": ev.status},
                         "evidence_validated", None, prior=steps)
    return {"web_evidence": ev, "steps": steps}


def node_candidate(state: WorkflowState) -> dict:
    state = _S(state)
    steps = _record_step(state, "candidate_generation", "in_progress", None, "candidates_started", None)

    merged = _merge_avoid_feedback(state.officer_feedback, state.auto_avoid_windows)
    structured = [ReplanningConstraint(**c) for c in state.replanning_constraints] if state.replanning_constraints else None
    if not structured and state.officer_feedback:
        structured = structured_constraints_from_feedback(state.officer_feedback)

    result = candidate_generator.run(
        state.request,
        _d(state.maintenance_analysis),
        _d(state.traffic_analysis),
        _d(state.historical_analysis),
        officer_feedback=merged,
        structured_constraints=structured,
    )
    steps = _record_step(state, "candidate_generation", "completed",
                         {"candidates": len(_d(result).get("candidates", []))},
                         "candidates_generated", None, prior=steps)
    # First pass leaves retry_count at 0; replan loop passes increment it.
    retry_count = (state.retry_count + 1) if state.candidate_windows is not None else 0
    return {"candidate_windows": result, "steps": steps, "retry_count": retry_count}


def node_optimize(state: WorkflowState) -> dict:
    state = _S(state)
    steps = _record_step(state, "cp_sat_optimization", "in_progress", None, "optimization_started", None)
    result = cp_sat_optimizer.run(
        _d(state.candidate_windows).get("candidates", []),
        state.request,
        _d(state.traffic_analysis),
    )
    steps = _record_step(state, "cp_sat_optimization", "completed",
                         {"feasible": _d(result).get("feasible", False),
                          "status": _d(result).get("solver_status", "UNKNOWN")},
                         "optimization_completed", None, prior=steps)
    return {"optimization_result": result, "steps": steps}


def after_optimize(state: WorkflowState) -> str:
    state = _S(state)
    if not (state.optimization_result and state.optimization_result.feasible):
        return "fail"
    return "simulate"


def node_simulate(state: WorkflowState) -> dict:
    state = _S(state)
    selected = _d(state.optimization_result).get("selected_window", {})
    steps = _record_step(state, "simulation", "in_progress", None, "simulation_started", None)
    result = simulator.run(selected, state.trains, state.request)
    steps = _record_step(state, "simulation", "completed",
                         {"affected": _d(result).get("total_trains_affected", 0),
                          "delay": _d(result).get("total_delay_minutes", 0)},
                         "simulation_completed", None, prior=steps)
    return {"simulation_result": result, "steps": steps}


def node_routing(state: WorkflowState) -> dict:
    state = _S(state)
    steps = _record_step(state, "routing_analysis", "in_progress", None, "routing_started", None)
    result = routing_agent.run(state.request, state.simulation_result, state.traffic_analysis)
    steps = _record_step(state, "routing_analysis", "completed",
                         {"options": len(_d(result).get("options", []))},
                         "routing_completed", None, prior=steps)
    return {"routing_analysis": result, "steps": steps}


def node_route_optimize(state: WorkflowState) -> dict:
    state = _S(state)
    steps = _record_step(state, "route_optimization", "in_progress", None, "routing_started", None)
    result = route_optimizer.run(state.routing_analysis, state.simulation_result, state.request)
    steps = _record_step(state, "route_optimization", "completed",
                         {"feasible": _d(result).get("feasible", False),
                          "rerouted": _d(result).get("trains_rerouted", 0)},
                         "routing_completed", None, prior=steps)
    return {"routing_optimization": result, "steps": steps}


def node_gate(state: WorkflowState) -> dict:
    state = _S(state)
    """Deterministic Hard-Conflict Gate."""
    routing = _d(state.routing_optimization) or {}
    conflicts = routing.get("conflicts", [])
    steps = list(state.steps)

    if conflicts:
        sim_by_train = {t.get("train_number"): t for t in _d(state.simulation_result).get("affected_trains", [])}
        new_avoid = []
        for c in conflicts:
            t = sim_by_train.get(c.get("train_number"), {})
            start = _to_minutes(t.get("scheduled_arrival") or "00:00")
            end = _to_minutes(t.get("scheduled_departure") or "00:00")
            if end <= start:
                end = start + 30
            new_avoid.append((start, end))
            state.auto_avoid_windows.append([start, end])
        state.replanning_constraints.append(ReplanningConstraint(
            type="AVOID_WINDOW", start=to_time_str(new_avoid[-1][0]), end=to_time_str(new_avoid[-1][1]),
            reason=f"Hard conflict: premium train delayed > {HARD_PREMIUM_DELAY_MIN} min", source="AUTO",
        ).model_dump())
        steps = _record_step(state, "hard_conflict_gate", "completed",
                             {"hard_conflict": True, "conflicts": len(conflicts),
                              "added_avoid": [_window_str(s, e) for s, e in new_avoid]},
                             "hard_conflict_detected", None)
    else:
        steps = _record_step(state, "hard_conflict_gate", "completed",
                             {"hard_conflict": False}, "gate_passed", None)

    return {"routing_optimization": _unwrap(state.routing_optimization),
            "auto_avoid_windows": state.auto_avoid_windows,
            "replanning_constraints": state.replanning_constraints,
            "auto_replanned": state.auto_replanned or bool(conflicts),
            "steps": steps}


def _unwrap(value):
    return value


def after_gate(state: WorkflowState) -> str:
    state = _S(state)
    routing = _d(state.routing_optimization) or {}
    conflicts = routing.get("conflicts", [])
    if conflicts:
        if state.retry_count + 1 < state.max_retries:
            return "candidate"
        return "fail"
    return "validate_constraints"


def node_constraints(state: WorkflowState) -> dict:
    state = _S(state)
    steps = _record_step(state, "constraint_validation", "in_progress", None, "validation_started", None)
    selected = _d(state.optimization_result).get("selected_window", {})
    structured = [ReplanningConstraint(**c) for c in state.replanning_constraints] if state.replanning_constraints else None
    merged = _merge_avoid_feedback(state.officer_feedback, state.auto_avoid_windows)
    result = constraint_validator.run(
        selected, state.request,
        _d(state.traffic_analysis), _d(state.maintenance_analysis),
        officer_feedback=merged, simulation_result=_d(state.simulation_result),
        structured_constraints=structured)
    steps = _record_step(state, "constraint_validation", "completed",
                         {"valid": _d(result).get("valid", False)}, "constraint_validation_completed", None, prior=steps)
    return {"constraint_validation": result, "steps": steps}


def after_constraints(state: WorkflowState) -> str:
    state = _S(state)
    if state.constraint_validation and state.constraint_validation.valid:
        return "risk"
    if state.retry_count + 1 < state.max_retries:
        return "candidate"
    return "fail"


def node_risk(state: WorkflowState) -> dict:
    state = _S(state)
    steps = _record_step(state, "risk_compliance", "in_progress", None, "agent_started", None)
    result = risk_agent.run(
        state.request, _d(state.simulation_result), _d(state.constraint_validation),
        _d(state.traffic_analysis), _d(state.historical_analysis))
    steps = _record_step(state, "risk_compliance", "completed",
                         {"risk_level": _d(result).get("risk_level", "MEDIUM"),
                          "score": _d(result).get("risk_score", 50)},
                         "risk_completed", None, prior=steps)
    return {"risk_analysis": result, "steps": steps}


def node_fusion(state: WorkflowState) -> dict:
    state = _S(state)
    steps = _record_step(state, "decision_fusion", "in_progress", None, "agent_started", None)
    result = decision_fusion_agent.run(
        _d(state.maintenance_analysis), _d(state.traffic_analysis), _d(state.priority_analysis),
        _d(state.historical_analysis), _d(state.optimization_result), _d(state.constraint_validation),
        _d(state.simulation_result), _d(state.risk_analysis), state.request,
        officer_feedback=state.officer_feedback)
    d = _d(result)
    steps = _record_step(state, "decision_fusion", "completed",
                         {"recommendation": d.get("recommendation", "RECOMMEND_REVIEW"),
                          "confidence": d.get("confidence", 85)},
                         "decision_fusion_completed", None, prior=steps)
    return {"decision": result, "steps": steps}


def node_report(state: WorkflowState) -> dict:
    state = _S(state)
    steps = _record_step(state, "report_generation", "in_progress", None, "report_started", None)
    report = _build_report(state)
    steps = _record_step(state, "report_generation", "completed",
                         {"report_id": f"RPT-{state.request_id}-V{state.plan_version}"},
                         "report_ready", None, prior=steps)
    # plan pending human review
    emit = _emit_for(state)
    if emit:
        try:
            emit("plan_pending_review", {"request_id": state.request_id,
                                         "plan_version": state.plan_version,
                                         "status": "PENDING_REVIEW"})
        except Exception:
            pass
    return {"report": report, "workflow_status": "REPORT_READY", "steps": steps}


def node_fail(state: WorkflowState) -> dict:
    state = _S(state)
    reason = state.errors[-1] if state.errors else "Workflow could not produce a feasible, compliant plan within retry bounds."
    steps = _record_step(state, "workflow_failed", "failed", {"reason": reason},
                         "workflow_failed", None)
    return {"workflow_status": "FAILED", "errors": state.errors + [reason], "steps": steps}


# ---------------------------------------------------------------------------
# Report builder (presentation only - never mutates the decision)
# ---------------------------------------------------------------------------


def _candidate_selected(c: dict, selected: dict) -> bool:
    return (c.get("start_time") == selected.get("start_time")
            and c.get("end_time") == selected.get("end_time"))


def _window_rejection_reasons(c: dict, sel: dict) -> List[str]:
    """Deterministic rejection rationale, derived only from candidate figures."""
    reasons = []
    if (c.get("affected_trains") or 0) > (sel.get("affected_trains") or 0):
        reasons.append(f"More trains affected ({c.get('affected_trains')} vs {sel.get('affected_trains')} for the selected window)")
    if (c.get("estimated_delay_minutes") or 0) > (sel.get("estimated_delay_minutes") or 0):
        reasons.append(f"Higher total delay ({c.get('estimated_delay_minutes')} min vs {sel.get('estimated_delay_minutes')} min)")
    if (c.get("score") or 0) < (sel.get("score") or 0):
        reasons.append(f"Lower CP-SAT objective score ({c.get('score')} vs {sel.get('score')})")
    if not c.get("within_preferred"):
        reasons.append("Falls outside the engineer's preferred time range")
    if not reasons:
        reasons.append("Not chosen as the best-compromise feasible window by CP-SAT optimization")
    return reasons


def _train_explanation(t: dict, selected: dict, decided: dict) -> str:
    arr = t.get("scheduled_arrival") or t.get("arrival_time") or ""
    dep = t.get("scheduled_departure") or t.get("departure_time") or ""
    delay = float(t.get("delay_minutes") or 0)
    action = decided.get("action") or t.get("action") or t.get("status") or "DELAY"
    note = decided.get("note") or ""
    block = f"{selected.get('start_time')}-{selected.get('end_time')}"
    if note:
        return (f"Scheduled {arr}-{dep} intersects block {block}; regulated as {action} "
                f"(deterministic simulation: {delay} min). {note}")
    return (f"Scheduled {arr}-{dep} intersects block {block}; deterministic simulation "
            f'yields {delay} min delay (action: {action}).')


def _risk_mitigation(risk: dict, kind: str, magnitude) -> str:
    mitigations = risk.get("mitigations", []) or []
    n = float(magnitude or 0)
    if kind == "maintenance" and n > 0:
        return next((m for m in mitigations if "route" in m.lower()),
                    "Verify alternative route availability before the block starts.")
    if kind in ("traffic", "operational") and n > 0:
        return next((m for m in mitigations if "notification" in m.lower() or "split" in m.lower()),
                    "Issue advance notice to train controllers and monitor cascading delays.")
    if kind in ("safety", "compliance") and n > 0:
        return "Resolve the flagged violations/warnings before the block may be authorised."
    return "No additional mitigation flagged by the deterministic risk assessment for this category."


def _build_officer_report(req: dict, selected: dict, sim: dict, risk: dict, fusion: dict,
                          constraints: dict, traffic: dict, historical: dict,
                          maintenance: dict, priority_analysis: dict, candidates: dict,
                          routing: dict, routing_opt: dict, rag: dict, web: dict,
                          optimization: dict, auto_replanned: bool, retry_count: int,
                          officer_feedback: Optional[dict]) -> dict:
    """Officer Plan Review explanation: a deterministic 10-section report.

    Every figure and reason comes from actual workflow outputs (timetable,
    simulation, CP-SAT, compliance, risk, routes, RAG/historical/Web evidence).
    No schedule, delay, constraint, route, risk value or reason is invented here.
    """
    affected = sim.get("affected_trains", []) or []
    affected_count = len(affected)
    delay = float(sim.get("total_delay_minutes") or 0)
    max_delay = float(sim.get("max_delay_minutes") or 0)
    rerouted = int(sim.get("trains_rerouted") or 0)
    held = int(sim.get("trains_held") or 0)
    risk_score = float(risk.get("risk_score") or 0)
    risk_level = risk.get("risk_level", "MEDIUM")
    passed_checks = constraints.get("passed_constraints", []) or []
    warn_checks = constraints.get("warnings", []) or []
    viol_checks = constraints.get("violations", []) or []
    passed_count = len(passed_checks)
    warn_count = len(warn_checks)
    viol_count = len(viol_checks)
    sel_start = selected.get("start_time", "N/A")
    sel_end = selected.get("end_time", "N/A")

    candidates_list = candidates.get("candidates", []) or []
    sel_cand = next((c for c in candidates_list if _candidate_selected(c, selected)), {})

    # ---- Executive Recommendation -----------------------------------------
    rec_disposition = {
        "RECOMMEND_APPROVE": "APPROVE",
        "RECOMMEND_REVIEW": "REVIEW",
        "RECOMMEND_REJECT": "REJECT",
    }.get(str(fusion.get("recommendation", "")).upper(), "REVIEW")

    # ---- Why This Block Was Selected --------------------------------------
    why_supplement = []
    if constraints.get("valid"):
        why_supplement.append(f"All {passed_count} deterministic compliance checks passed with zero violations")
    else:
        why_supplement.append(f"{viol_count} compliance violation(s) remain flagged for verification")
    if auto_replanned:
        why_supplement.append(f"Window revised automatically {retry_count} time(s) after the hard-conflict gate")
    if officer_feedback and officer_feedback.get("rejection_reason"):
        avoid = officer_feedback.get("avoid_time", "")
        why_supplement.append(f"Avoids officer-restricted window{'s' if avoid else ''}"
                              + (f" {avoid}" if avoid else " from the previous rejection"))
    tradeoffs = list(fusion.get("tradeoffs", []) or [])
    if delay > 10:
        tradeoffs.append(f"{affected_count} train(s) incur a combined delay of {delay} min to accommodate the block")

    # ---- Train-by-Train Impact --------------------------------------------
    final_by_train = {o.get("train_number"): o for o in routing_opt.get("options", []) or []}
    prop_by_train = {o.get("train_number"): o for o in routing.get("options", []) or []}
    train_impact = [
        {
            "train_number": t.get("train_number"),
            "train_name": t.get("train_name", ""),
            "train_type": t.get("train_type", ""),
            "priority": t.get("priority", ""),
            "scheduled_arrival": t.get("scheduled_arrival") or t.get("arrival_time"),
            "scheduled_departure": t.get("scheduled_departure") or t.get("departure_time"),
            "delay_minutes": round(float(t.get("delay_minutes") or 0), 1),
            "action": t.get("action") or t.get("status") or "DELAY",
            "regulation": (final_by_train.get(t.get("train_number"), {}) or {}).get("action", "NORMAL"),
            "explanation": _train_explanation(t, selected, final_by_train.get(t.get("train_number"), {}) or {}),
        }
        for t in affected
    ]

    # ---- Alternative Windows ----------------------------------------------
    alt_windows = []
    for c in candidates_list:
        is_sel = _candidate_selected(c, selected)
        alt_windows.append({
            "window": f"{c.get('start_time')}-{c.get('end_time')}",
            "duration_minutes": c.get("duration_minutes"),
            "affected_trains": c.get("affected_trains", 0),
            "estimated_delay_minutes": round(float(c.get("estimated_delay_minutes") or 0), 1),
            "score": c.get("score", 0),
            "within_preferred": bool(c.get("within_preferred")),
            "avoids_officer_constraint": bool(c.get("avoids_officer_constraint")),
            "verdict": "SELECTED" if is_sel else "REJECTED",
            "basis": (["Selected by CP-SAT as optimal among the feasible candidates"]
                      if is_sel else _window_rejection_reasons(c, sel_cand)),
        })

    # ---- Alternative Routing / Regulation ---------------------------------
    routing_alternatives = [
        {
            "train_number": t.get("train_number"),
            "train_name": t.get("train_name", ""),
            "priority": t.get("priority", ""),
            "delay_minutes": round(float(t.get("delay_minutes") or 0), 1),
            "proposed_action": (prop_by_train.get(t.get("train_number"), {}) or {}).get("action", "NORMAL"),
            "proposed_reasoning": (prop_by_train.get(t.get("train_number"), {}) or {}).get("reasoning", ""),
            "decided_action": (final_by_train.get(t.get("train_number"), {}) or {}).get("action", "NORMAL"),
            "feasible": bool((final_by_train.get(t.get("train_number"), {}) or {}).get("feasible", True)),
            "note": (final_by_train.get(t.get("train_number"), {}) or {}).get("note", ""),
            "additional_delay": round(float((final_by_train.get(t.get("train_number"), {}) or {}).get("additional_delay")
                                            or t.get("delay_minutes") or 0), 1),
        }
        for t in affected
    ]

    # ---- Constraints Considered -------------------------------------------
    constraints_report = {
        "valid": bool(constraints.get("valid")),
        "satisfied": [{"rule": p.get("rule"), "detail": p.get("detail", "")} for p in passed_checks],
        "warnings": [{"rule": w.get("rule"), "detail": w.get("detail", "")} for w in warn_checks],
        "violations": [{"rule": v.get("rule"), "detail": v.get("detail", "")} for v in viol_checks],
    }

    # ---- Safety & Risk Explanation ----------------------------------------
    risk_categories = [
        {
            "type": "Safety",
            "score": round(float(risk.get("safety_risk") or 0), 1),
            "status": "PASS" if viol_count == 0 else "VIOLATION",
            "basis": ("No constraint violations raised by the deterministic compliance validator"
                      if viol_count == 0 else "; ".join(v.get("detail", "") for v in viol_checks)),
            "mitigation": _risk_mitigation(risk, "safety", viol_count),
        },
        {
            "type": "Traffic & Passenger",
            "score": round(float(risk.get("passenger_impact") or 0), 1),
            "status": "PASS" if delay <= 30 else "WARNING",
            "basis": f"{affected_count} train(s) affected with {delay} min total delay from block-window simulation",
            "mitigation": _risk_mitigation(risk, "traffic", delay),
        },
        {
            "type": "Maintenance",
            "score": round(float(risk.get("maintenance_risk") or 0), 1),
            "status": "PASS" if rerouted <= 2 else "WARNING",
            "basis": ("No re-routing required; maintenance is contained to the declared block"
                      if rerouted == 0 else f"{rerouted} train(s) require re-routing during the maintenance work"),
            "mitigation": _risk_mitigation(risk, "maintenance", rerouted),
        },
        {
            "type": "Operational",
            "score": round(float(risk.get("operational_risk") or 0), 1),
            "status": "PASS" if delay <= 60 and rerouted <= 2 else "WARNING",
            "basis": f"Operational load: {delay} min total delay, {rerouted} reroute(s), {held} hold(s)",
            "mitigation": _risk_mitigation(risk, "operational", delay),
        },
        {
            "type": "Compliance",
            "score": None,
            "status": risk.get("compliance_status", "UNKNOWN"),
            "basis": f"{passed_count} rule checks passed, {warn_count} warnings, {viol_count} violations",
            "mitigation": _risk_mitigation(risk, "compliance", viol_count),
        },
    ]

    # ---- Evidence & Sources -----------------------------------------------
    sim_items = [
        f"Train {t.get('train_number')} ({t.get('train_name', '')}): scheduled "
        f"{t.get('scheduled_arrival', t.get('arrival_time'))}-{t.get('scheduled_departure', t.get('departure_time'))} on "
        f"{req.get('section', '')}; +{round(float(t.get('delay_minutes') or 0), 1)} min; action "
        f"{t.get('action', t.get('status', 'DELAY'))}."
        for t in affected[:12]
    ]
    rag_docs = rag.get("documents", []) or []
    hist_cases = historical.get("similar_cases", []) or []
    web_sources = web.get("sources", []) or []
    web_items = []
    if web.get("summary"):
        web_items.append(web.get("summary"))
    for s in web_sources[:6]:
        web_items.append(s.get("title") or s.get("source_url") or s.get("url") or "source")
    routing_items = [
        f"Train {o.get('train_number')}: proposed {o.get('proposed_action')} -> decided {o.get('decided_action')}"
        + (f" ({o.get('note', '')})" if o.get("note") else "")
        for o in routing_alternatives
    ]
    evidence_sources = [
        {
            "source": "Timetable & Deterministic Simulation",
            "tag": "FACT",
            "detail": sim.get("summary", ""),
            "items": sim_items,
        },
        {
            "source": "CP-SAT Optimization",
            "tag": "CALCULATION",
            "detail": (f"Selected {sel_start}-{sel_end} with objective score {optimization.get('objective_score', 0)} "
                       f"(solver {optimization.get('solver_status', 'UNKNOWN')}); "
                       f"{candidates.get('total_evaluated', 0)} candidate windows evaluated."),
            "items": [
                f"{c.get('start_time')}-{c.get('end_time')} score {c.get('score')}, "
                f"{c.get('affected_trains')} train(s), {c.get('estimated_delay_minutes')} min"
                for c in candidates_list
            ],
        },
        {
            "source": "RAG - Railway Policy Retrieval",
            "tag": "FACT",
            "detail": f"RAG engine {rag.get('engine', 'faiss')}: {rag.get('total_retrieved', 0)} document(s) "
                      f"retrieved for '{rag.get('query', '')}'",
            "items": [f"{d.get('title', '')} ({d.get('source', '')})" for d in rag_docs[:6]],
        },
        {
            "source": "Historical Case Evidence",
            "tag": "FACT",
            "detail": f"{len(hist_cases)} similar case(s); historical approval rate "
                      f"{historical.get('historical_outcomes', {}).get('approval_rate', 'n/a')}%",
            "items": [
                f"{c.get('proposed_window', '')} on {c.get('section', '')}: {c.get('outcome', '')}, "
                f"{c.get('affected_trains', 0)} train(s), {c.get('delay_minutes', 0)} min delay"
                for c in hist_cases
            ],
        },
        {
            "source": "Tavily Web Research",
            "tag": "AI RECOMMENDATION",
            "detail": (f"{web.get('relevant_results', 0)} relevant result(s) across "
                       f"{web.get('total_searches', 0)} search(es)"
                       if (web.get("status") or "idle") != "failed"
                       else f"Web search failed: {web.get('error', '')}"),
            "items": web_items,
        },
        {
            "source": "Routing Agent Proposals & Route Optimizer",
            "tag": "AI RECOMMENDATION",
            "detail": f"{len(routing.get('options', []) or [])} alternative(s) proposed; the route optimizer decided "
                      f"for {len(routing_opt.get('options', []) or [])} affected train(s).",
            "items": routing_items,
        },
    ]

    # ---- AI Agent Findings -------------------------------------------------
    agent_findings = [
        {"agent": "maintenance_agent", "role": "Maintenance Requirements",
         "summary": maintenance.get("summary", ""),
         "metrics": {"urgency": maintenance.get("urgency", "MEDIUM"),
                     "resources": len(maintenance.get("resource_requirements", []) or []),
                     "duration_minutes": maintenance.get("maintenance_duration")}},
        {"agent": "traffic_agent", "role": "Timetable & Conflict Screening",
         "summary": traffic.get("summary", ""),
         "metrics": {"affected_trains": traffic.get("total_affected", 0),
                     "estimated_delay_minutes": traffic.get("total_estimated_delay", 0),
                     "impact_class": traffic.get("estimated_impact", "LOW")}},
        {"agent": "priority_agent", "role": "Priority & Urgency Assessment",
         "summary": priority_analysis.get("reason", "Standard priority assessment"),
         "metrics": {"priority_level": priority_analysis.get("priority_level", "MEDIUM"),
                     "priority_score": priority_analysis.get("priority_score", 0),
                     "safety_criticality": priority_analysis.get("safety_criticality", 0)}},
        {"agent": "historical_agent", "role": "Historical Precedent & Rules",
         "summary": historical.get("summary", ""),
         "metrics": {"similar_cases": len(hist_cases),
                     "approval_rate": historical.get("historical_outcomes", {}).get("approval_rate")}},
        {"agent": "rag_retrieval", "role": "Railway Policy Retrieval",
         "summary": f"Retrieved {rag.get('total_retrieved', 0)} policy/reference document(s) via {rag.get('engine', 'faiss')}",
         "metrics": {"documents_retrieved": rag.get("total_retrieved", 0)}},
        {"agent": "cp_sat_optimization", "role": "Deterministic Optimization",
         "summary": f"Selected {sel_start}-{sel_end}; solver {optimization.get('solver_status', 'UNKNOWN')}",
         "metrics": {"objective_score": optimization.get("objective_score", 0),
                     "candidates_evaluated": candidates.get("total_evaluated", 0)}},
        {"agent": "simulation", "role": "Deterministic Block Simulation",
         "summary": sim.get("summary", ""),
         "metrics": {"affected_trains": affected_count, "total_delay_minutes": delay,
                     "max_delay_minutes": max_delay, "rerouted": rerouted, "held": held}},
        {"agent": "web_research", "role": "External Evidence Research",
         "summary": (web.get("summary", "")
                     or f"{web.get('relevant_results', 0)} relevant result(s) across {web.get('total_searches', 0)} search(es)"),
         "metrics": {"sources": len(web_sources), "status": web.get("status", "idle")}},
        {"agent": "routing_agent", "role": "Routing & Regulation Proposal",
         "summary": routing.get("summary", ""),
         "metrics": {"options_proposed": len(routing.get("options", []) or [])}},
        {"agent": "constraint_validation", "role": "Compliance Validation",
         "summary": (f"Compliance summary: {passed_count} passed, {warn_count} warning(s), {viol_count} violation(s)"
                     if constraints.get("total_checks") else f"Valid: {bool(constraints.get('valid'))}"),
         "metrics": {"valid": bool(constraints.get("valid")), "total_checks": constraints.get("total_checks", 0)}},
        {"agent": "risk_compliance", "role": "Risk Assessment",
         "summary": risk.get("summary", ""),
         "metrics": {"risk_level": risk_level, "risk_score": risk_score,
                     "compliance_status": risk.get("compliance_status", "UNKNOWN")}},
        {"agent": "decision_fusion", "role": "Advisory Decision Fusion",
         "summary": fusion.get("reasoning_summary", ""),
         "metrics": {"recommendation": fusion.get("recommendation", "RECOMMEND_REVIEW"),
                     "confidence": fusion.get("confidence", 85),
                     "authority": fusion.get("approval_authority", "OFFICER")}},
    ]

    # ---- Final Decision ----------------------------------------------------
    benefits = []
    if constraints.get("valid"):
        benefits.append(f"All {passed_count} deterministic compliance checks passed with zero violations")
    else:
        benefits.append(f"{passed_count} check(s) passed; {viol_count} violation(s) flagged for officer attention")
    benefits.append(f"CP-SAT optimal window {sel_start}-{sel_end} ({selected.get('duration_minutes')} min) "
                    f"satisfies the required {req.get('duration_minutes')} min maintenance duration")
    benefits.append(f"Predicted impact: {affected_count} train(s), {delay} min total delay, "
                    f"{max_delay} min worst-case, {rerouted} reroute(s)")
    if auto_replanned:
        benefits.append(f"Auto-replanned {retry_count} time(s) to avoid hard-conflicting premium trains before review")
    if officer_feedback and officer_feedback.get("rejection_reason"):
        benefits.append("Officer-restricted windows from the previous rejection were respected")

    residual_risks = list(risk.get("warnings", []) or [])
    if viol_count:
        residual_risks.insert(0, f"{viol_count} constraint violation(s) remain: "
                                  + "; ".join(v.get("detail", "") for v in viol_checks[:3]))

    conditions = []
    if delay > 15:
        conditions.append("Issue advance notification to affected train controllers")
    if rerouted > 0:
        conditions.append("Verify alternative route availability and capacity before block start")
    if (req.get("weather_sensitive") or "NO").upper() == "YES":
        conditions.append("Re-confirm weather conditions before commencing weather-sensitive work")
    if viol_count:
        conditions.append("Resolve the flagged violations before the block may be authorised")
    conditions.append("Confirm the section is clear and formally handed over to the maintenance team before block start")

    return {
        "generated_for": "officer-review",
        "grounding": ("All figures in this report are actual workflow outputs (timetable, deterministic simulation, "
                      "CP-SAT, compliance, risk, routes, evidence). No schedule, delay, constraint, route, risk value "
                      "or reason is invented."),
        "executive": {
            "block_window": f"{sel_start}-{sel_end}",
            "date": req.get("requested_date"),
            "section": req.get("section"),
            "track_no": req.get("track_no"),
            "location": req.get("location"),
            "maintenance_type": req.get("maintenance_type"),
            "duration_minutes": selected.get("duration_minutes", req.get("duration_minutes")),
            "affected_trains": affected_count,
            "total_delay_minutes": delay,
            "max_delay_minutes": max_delay,
            "rerouted": rerouted,
            "held": held,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "confidence": fusion.get("confidence", 85),
            "solver_status": optimization.get("solver_status", "UNKNOWN"),
            "recommendation": rec_disposition,
            "auto_replanned": bool(auto_replanned),
            "retry_count": retry_count,
        },
        "selection_rationale": {
            "reasons": list(fusion.get("why_this_window", []) or []) + why_supplement,
            "tradeoffs": tradeoffs,
            "alternative_windows_considered": len(candidates_list),
            "preferred_window": f"{req.get('preferred_start')}-{req.get('preferred_end')}",
        },
        "train_impact": train_impact,
        "alternative_windows": alt_windows,
        "routing_alternatives": routing_alternatives,
        "constraints": constraints_report,
        "risk": {
            "overall_score": risk_score,
            "risk_level": risk_level,
            "categories": risk_categories,
            "warnings": risk.get("warnings", []),
            "mitigations": risk.get("mitigations", []),
        },
        "agent_findings": agent_findings,
        "evidence_sources": evidence_sources,
        "final_decision": {
            "authority": fusion.get("approval_authority", "OFFICER"),
            "advisory": fusion.get("recommendation", "RECOMMEND_REVIEW"),
            "weight_of_evidence": ("CP-SAT, deterministic validation and simulation are authoritative for this plan; "
                                   "the AI only explains their outputs and never changes them."),
            "benefits": benefits,
            "residual_risks": residual_risks,
            "mitigations": list(risk.get("mitigations", []) or []),
            "conditions": conditions,
        },
    }


def _build_report(state: WorkflowState) -> dict:
    selected = _d(state.optimization_result).get("selected_window", {}) if state.optimization_result else {}
    sim = _d(state.simulation_result) or {}
    risk = _d(state.risk_analysis) or {}
    fusion = _d(state.decision) or {}
    constraints = _d(state.constraint_validation) or {}
    traffic = _d(state.traffic_analysis) or {}
    historical = _d(state.historical_analysis) or {}
    priority = _d(state.priority_analysis) or {}
    maintenance = _d(state.maintenance_analysis) or {}
    candidates = _d(state.candidate_windows) or {}
    routing = _d(state.routing_analysis) or {}
    routing_opt = _d(state.routing_optimization) or {}
    rag = _d(state.rag_evidence) or {}
    web = _d(state.web_evidence) or {}
    req = state.request or {}

    officer_report = _build_officer_report(
        req, selected, sim, risk, fusion, constraints, traffic, historical,
        maintenance, priority, candidates, routing, routing_opt, rag, web,
        _d(state.optimization_result) or {},
        bool(state.auto_replanned), state.retry_count, state.officer_feedback,
    )

    return {
        "officer_report": officer_report,
        "request_summary": {
            "id": req.get("id"),
            "department": req.get("department"),
            "maintenance_type": req.get("maintenance_type"),
            "section": req.get("section"),
            "location": req.get("location"),
            "duration": req.get("duration_minutes"),
            "priority": req.get("priority"),
            "date": req.get("requested_date"),
        },
        "request_context": {
            "work_type": req.get("work_type"),
            "track_no": req.get("track_no"),
            "equipment": req.get("equipment"),
            "crew_size": req.get("crew_size"),
            "est_material_cost": req.get("est_material_cost"),
            "weather_sensitive": req.get("weather_sensitive"),
            "special_instructions": req.get("special_instructions"),
            "preferred_window": (f"{req.get('preferred_start')}-{req.get('preferred_end')}"
                                 if req.get("preferred_start") else None),
        },
        "cost_estimate": {
            "currency": "INR",
            "material_cost": req.get("est_material_cost"),
            "crew_size": req.get("crew_size"),
            "estimated_crew_hours": (round(float(req.get("duration_minutes") or 0) / 60.0
                                           * float(req.get("crew_size") or 0), 1)
                                     if req.get("crew_size") else None),
            "note": ("Cost is derived from declared inputs only; procurement, "
                     "overtime and material actuals are not forecast."),
        },
        "ai_replanning": {
            "auto_replanned": bool(state.auto_replanned),
            "avoid_windows": [_window_str(w[0], w[1]) for w in state.auto_avoid_windows],
            "avoid_windows_raw": [{"start_m": w[0], "end_m": w[1]} for w in state.auto_avoid_windows],
            "retry_count": state.retry_count,
            "note": ("AI automatically regenerated a compliant window to avoid "
                     "hard-conflicting premium trains before presenting to the officer."
                     if state.auto_replanned else None),
        },
        "recommended_block": {
            "date": req.get("requested_date"),
            "start_time": selected.get("start_time"),
            "end_time": selected.get("end_time"),
            "duration_minutes": selected.get("duration_minutes"),
            "section": req.get("section"),
        },
        "why_this_window": fusion.get("why_this_window", []),
        "candidate_comparison": [
            {"start": c.get("start_time"), "end": c.get("end_time"),
             "score": c.get("score"), "affected_trains": c.get("affected_trains"),
             "estimated_delay_minutes": c.get("estimated_delay_minutes")}
            for c in candidates.get("candidates", [])
        ],
        "train_impact": {
            "affected_trains": sim.get("affected_trains", []),
            "total_affected": sim.get("total_trains_affected", 0),
            "total_delay": sim.get("total_delay_minutes", 0),
            "max_delay": sim.get("max_delay_minutes", 0),
            "rerouted": sim.get("trains_rerouted", 0),
            "held": sim.get("trains_held", 0),
        },
        "impact_rows": [
            {
                "train_number": t.get("train_number"),
                "train_name": t.get("train_name"),
                "train_type": t.get("train_type"),
                "scheduled_arrival": t.get("scheduled_arrival") or t.get("arrival_time"),
                "scheduled_departure": t.get("scheduled_departure") or t.get("departure_time"),
                "projected_arrival": t.get("projected_arrival"),
                "delay_minutes": t.get("delay_minutes") or t.get("estimated_delay_minutes") or 0,
                "action": t.get("action") or t.get("status") or "INFO",
                "impact": t.get("impact"),
            }
            for t in sim.get("affected_trains", [])
        ],
        "alternative_routing_considered": routing_opt.get("options", []),
        "optimization": {
            "candidates_evaluated": candidates.get("total_evaluated", 0),
            "selected_window": f"{selected.get('start_time', 'N/A')}-{selected.get('end_time', 'N/A')}",
            "objective_score": _d(state.optimization_result).get("objective_score", 0),
            "solver_status": _d(state.optimization_result).get("solver_status", "UNKNOWN"),
            "route_optimization": {
                "trains_rerouted": routing_opt.get("trains_rerouted", 0),
                "trains_held": routing_opt.get("trains_held", 0),
                "total_additional_delay": routing_opt.get("total_additional_delay", 0),
                "summary": routing_opt.get("summary", ""),
            },
        },
        "safety_compliance": {
            "valid": constraints.get("valid", False),
            "passed": constraints.get("passed_constraints", []),
            "violations": constraints.get("violations", []),
            "warnings": constraints.get("warnings", []),
        },
        "risk": {
            "overall_score": risk.get("risk_score", 0),
            "risk_level": risk.get("risk_level", "MEDIUM"),
            "safety_risk": risk.get("safety_risk", 0),
            "operational_risk": risk.get("operational_risk", 0),
            "passenger_impact": risk.get("passenger_impact", 0),
            "compliance_status": risk.get("compliance_status", "UNKNOWN"),
            "warnings": risk.get("warnings", []),
            "mitigations": risk.get("mitigations", []),
        },
        "historical_evidence": {
            "similar_cases": historical.get("similar_cases", [])[:3],
            "approval_rate": historical.get("historical_outcomes", {}).get("approval_rate", 80),
            "recommendations": historical.get("recommendations", []),
        },
        "rag_evidence": {
            "query": rag.get("query", ""),
            "total_retrieved": rag.get("total_retrieved", 0),
            "engine": rag.get("engine", "faiss"),
            "documents": rag.get("documents", []),
        },
        "web_research_evidence": {
            "status": web.get("status", "idle"),
            "query": web.get("query", ""),
            "total_searches": web.get("total_searches", 0),
            "relevant_results": web.get("relevant_results", 0),
            "search_count": web.get("search_count", 0),
            "sources": web.get("sources", [])[:8],
            "summary": web.get("summary", ""),
            "error": web.get("error"),
            "sample": web.get("sample", False),
            "note": "Web information is evidence only and does not modify "
                    "constraints, schedules, or the deterministic plan decision.",
        },
        "ai_explanation": fusion.get("reasoning_summary", ""),
        "ai_advisory": {
            "label": fusion.get("recommendation", "RECOMMEND_REVIEW"),
            "is_final": False,
            "approval_authority": fusion.get("approval_authority", "OFFICER"),
            "note": "This is AI-generated advice only. The AI cannot approve or publish a block. "
                    "Final approval is exclusively the officer's decision (officer-only endpoint).",
        },
        "key_factors": fusion.get("key_factors", []),
        "tradeoffs": fusion.get("tradeoffs", []),
        "confidence": fusion.get("confidence", 85),
        "decision_evidence": fusion.get("evidence", {}),
        "priority_analysis": priority,
        "agent_assessments": {
            "maintenance_agent": {
                "analysis": maintenance.get("summary", ""),
                "criticality": maintenance.get("urgency", "MEDIUM"),
                "recommended_window": f"{maintenance.get('preferred_start', '')}-{maintenance.get('preferred_end', '')}",
                "notes": [],
            },
            "traffic_agent": {
                "affected": traffic.get("total_affected", 0),
                "estimated_delay": traffic.get("total_estimated_delay", 0),
                "peak_congestion": traffic.get("estimated_impact", "LOW"),
                "notes": [],
            },
            "routing_agent": {
                "proposals": len(routing.get("options", [])),
                "rerouted": routing_opt.get("trains_rerouted", 0),
                "summary": routing.get("summary", ""),
            },
            "risk_agent": {
                "score": risk.get("risk_score"),
                "level": risk.get("risk_level"),
                "mitigations": risk.get("mitigations", []),
            },
            "compliance_agent": {
                "valid": constraints.get("valid"),
                "passed": constraints.get("passed_constraints", []),
                "violations": constraints.get("violations", []),
                "warnings": constraints.get("warnings", []),
            },
        },
        "risk_management_plan": [{"mitigation": m} for m in risk.get("mitigations", [])],
        "weather": _weather_report(req),
        "timeline": {
            "created": datetime.utcnow().isoformat(),
            "simulation_completed": sim.get("execution_time", ""),
            "optimization_status": _d(state.optimization_result).get("solver_status", "UNKNOWN"),
            "auto_replan_cycles": state.retry_count,
        },
        "version": state.plan_version,
        "officer_feedback": state.officer_feedback if state.officer_feedback else None,
        "workflow_status": "REPORT_READY",
        "generated_at": datetime.utcnow().isoformat(),
    }


def _weather_report(request: Dict) -> Dict[str, Any]:
    try:
        from app.services.weather import get_weather
        w = get_weather(request.get("section", "Shivajinagar - Khadki"))
        sensitive = (request.get("weather_sensitive") or "NO").upper() == "YES"
        blocked = (w.get("precipitation_probability") or 0) > 60
        return {
            "source": w.get("source", "n/a"),
            "temperature_c": w.get("temperature_c"),
            "precipitation_probability": w.get("precipitation_probability"),
            "wind_kmh": w.get("wind_kmh"),
            "condition": w.get("condition"),
            "weather_sensitive_work": sensitive,
            "advisory": (
                "High precipitation probability - consider deferring or weatherproofing the work."
                if sensitive and blocked
                else ("Precipitation risk is low; work can proceed as planned."
                      if not blocked else "Moderate weather risk; standard precautions apply.")
            ),
        }
    except Exception:
        return {"source": "unavailable", "advisory": "Weather feed unavailable - manual verification advised."}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

_GRAPH = None


def _build_graph():
    g = StateGraph(WorkflowState)
    g.add_node("validate", node_validate)
    g.add_node("maintenance", node_maintenance)
    g.add_node("traffic", node_traffic)
    g.add_node("priority", node_priority)
    g.add_node("merge", node_merge)
    g.add_node("historical", node_historical)
    g.add_node("rag", node_rag)
    g.add_node("web_research", node_web_research)
    g.add_node("evidence", node_evidence)
    g.add_node("candidate", node_candidate)
    g.add_node("optimize", node_optimize)
    g.add_node("simulate", node_simulate)
    g.add_node("routing", node_routing)
    g.add_node("route_optimize", node_route_optimize)
    g.add_node("gate", node_gate)
    g.add_node("validate_constraints", node_constraints)
    g.add_node("risk", node_risk)
    g.add_node("fusion", node_fusion)
    g.add_node("report", node_report)
    g.add_node("fail", node_fail)

    g.add_edge(START, "validate")
    g.add_conditional_edges("validate", _validate_router,
                            ["maintenance", "traffic", "priority", "fail"])
    g.add_edge("maintenance", "merge")
    g.add_edge("traffic", "merge")
    g.add_edge("priority", "merge")
    g.add_edge("merge", "historical")
    g.add_edge("historical", "rag")
    g.add_edge("rag", "web_research")
    g.add_edge("web_research", "evidence")
    g.add_edge("evidence", "candidate")
    g.add_edge("candidate", "optimize")
    g.add_conditional_edges("optimize", after_optimize, {"simulate": "simulate", "fail": "fail"})
    g.add_edge("simulate", "routing")
    g.add_edge("routing", "route_optimize")
    g.add_edge("route_optimize", "gate")
    g.add_conditional_edges("gate", after_gate, {"candidate": "candidate", "validate_constraints": "validate_constraints", "fail": "fail"})
    g.add_conditional_edges("validate_constraints", after_constraints, {"risk": "risk", "candidate": "candidate", "fail": "fail"})
    g.add_edge("risk", "fusion")
    g.add_edge("fusion", "report")
    g.add_edge("report", END)
    g.add_edge("fail", END)
    return g.compile()


def _validate_router(state: WorkflowState):
    state = _S(state)
    """Route: invalid -> fail, else parallel Send fan-out."""
    if state.workflow_status == "FAILED":
        return "fail"
    return _branch_validate(state)


def _get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()
    return _GRAPH


def compile_graph():
    """LangGraph Platform / LangSmith Studio entry point."""
    return _get_graph()


# ---------------------------------------------------------------------------
# Public entry point (compatible with legacy callers)
# ---------------------------------------------------------------------------


def run_workflow(
    request_data: Dict[str, Any],
    trains: list,
    plan_version: int = 1,
    officer_feedback: Dict[str, Any] = None,
    emit_event=None,
) -> Dict[str, Any]:
    initial = state_from_dict(request_data)
    initial.plan_version = plan_version
    initial.trains = trains or []
    initial.officer_feedback = officer_feedback or None
    initial.max_retries = MAX_RETRIES
    initial.retry_count = 0
    initial.workflow_status = "RUNNING"
    initial.start_time = time.time()

    # incoming officer feedback becomes structured constraints up-front
    if officer_feedback:
        initial.replanning_constraints = [c.model_dump() for c in structured_constraints_from_feedback(officer_feedback)]

    # register the emitter under a serializable run_id (callables cannot live
    # inside the Pydantic graph state)
    run_id = f"{request_data.get('id', 0)}-{int(time.time() * 1000)}"
    initial.run_id = run_id
    if emit_event:
        _EMITTERS[run_id] = emit_event

    try:
        final = _get_graph().invoke(initial)
    except Exception as e:  # noqa: BLE001
        final = initial.model_copy(deep=True)
        final.workflow_status = "FAILED"
        final.errors = list(initial.errors) + [f"workflow exception: {e}"]
    finally:
        _EMITTERS.pop(run_id, None)

    return _to_result(final)


def _to_result(state) -> Dict[str, Any]:
    if not isinstance(state, WorkflowState):
        state = WorkflowState(**state)
    ok = state.workflow_status == "REPORT_READY" and state.report is not None
    report_data = _d(state.report) if state.report else {}
    obj = {
        "status": "REPORT_READY" if ok else "FAILED",
        "workflow_status": state.workflow_status,
        "plan_version": state.plan_version,
        "report": report_data,
        "selected_window": _d(state.optimization_result).get("selected_window", {}) if state.optimization_result else {},
        "optimization_result": _d(state.optimization_result) or {},
        "simulation_result": _d(state.simulation_result) or {},
        "risk_analysis": _d(state.risk_analysis) or {},
        "constraint_validation": _d(state.constraint_validation) or {},
        "decision_fusion": _d(state.decision) or {},
        "maintenance_analysis": _d(state.maintenance_analysis) or {},
        "traffic_analysis": _d(state.traffic_analysis) or {},
        "priority_analysis": _d(state.priority_analysis) or {},
        "historical_analysis": _d(state.historical_analysis) or {},
        "candidate_windows": _d(state.candidate_windows) or {},
        "rag_evidence": _d(state.rag_evidence) or {},
        "web_evidence": _d(state.web_evidence) or {},
        "routing_analysis": _d(state.routing_analysis) or {},
        "routing_optimization": _d(state.routing_optimization) or {},
        "replanning_constraints": state.replanning_constraints or [],
        "retry_count": state.retry_count,
        "agent_results": state.steps,
        "total_execution_time": round(time.time() - state.start_time, 3),
        "errors": state.errors,
    }
    if not ok:
        obj["error"] = state.errors[-1] if state.errors else "Workflow could not produce a feasible, compliant plan."
        if state.constraint_validation:
            obj["violations"] = _d(state.constraint_validation).get("violations", [])
    return obj