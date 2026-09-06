"""Alternative Routing & Regulation Agent.

The agent PROPOSES, it does not decide. For every affected train it proposes an
operational alternative from a fixed vocabulary (NORMAL / HOLD / DIVERT /
RESCHEDULE / NO_ACTION). A DIVERT may only reference a route_id that exists in
the network topology data - the agent is never allowed to invent a route.

The deterministic Route & Operations Optimizer decides whether a proposal is
feasible and which option to actually use.
"""
import os
import time
from typing import Any, Dict, List

from app.network import network_data
from app.schemas.workflow import RoutingAnalysis
from app.services.llm import chat, _extract_json

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true" or not os.getenv("GROQ_API_KEY", "")

ACTIONS = ("NORMAL", "HOLD", "DIVERT", "RESCHEDULE", "NO_ACTION")
PREMIUM = ("RAJDHANI", "SHATABDI", "VANDE_BHARAT")


def run(
    request: Dict[str, Any],
    simulation_result: Any,
    traffic_analysis: Any = None,
) -> RoutingAnalysis:
    """Propose routing/regulation alternatives for trains affected by the block.

    simulation_result may be a TrainImpact model or a dict with the same shape.
    """
    start = time.time()
    section = request.get("section", "")
    sim = simulation_result.model_dump() if hasattr(simulation_result, "model_dump") else (simulation_result or {})

    affected = sim.get("affected_trains", []) or []
    if not affected:
        return RoutingAnalysis(
            section=section,
            options=[],
            summary="No trains affected - no routing action required.",
            execution_time=round(time.time() - start, 3),
        )

    available_routes = network_data.alternate_routes_for(section)
    routes_brief = [
        {"id": r["id"], "name": r["name"], "path": r["path"],
         "add_minutes": r["add_minutes"], "available_capacity": r.get("spare_capacity")}
        for r in available_routes
    ]

    if not DEMO_MODE:
        proposals = _llm_propose(section, affected, routes_brief, sim, available_routes)
    else:
        proposals = _propose_deterministic(section, affected, available_routes)

    # Guard: a DIVERT against a route that does not exist in the network is
    # stripped back to HOLD. Determinism wins.
    cleaned = []
    for opt in proposals:
        if opt.get("action", "NORMAL").upper() == "DIVERT":
            rid = opt.get("route_id")
            if not network_data.route_exists(section, rid):
                opt = {**opt, "action": "HOLD",
                       "route_id": None,
                       "reasoning": (opt.get("reasoning", "") + " [route unknown in network - fallback to HOLD]")}
        elif opt.get("action", "NORMAL").upper() not in ACTIONS:
            opt = {**opt, "action": "NORMAL", "route_id": None}
        cleaned.append(opt)

    counts = {"DIVERT": 0, "HOLD": 0, "NORMAL": 0, "RESCHEDULE": 0, "NO_ACTION": 0}
    for o in cleaned:
        counts[o["action"]] = counts.get(o["action"], 0) + 1

    return RoutingAnalysis(
        section=section,
        options=cleaned,
        notes=[
            "Routing agent proposes alternatives only.",
            "Route feasibility is verified by the deterministic Route & Operations Optimizer.",
            "Only network-registered alternates are considered (no invented routes).",
        ],
        summary=f"Proposed operational alternatives for {len(cleaned)} trains: {counts}.",
        execution_time=round(time.time() - start, 3),
    )


def _propose_deterministic(
    section: str,
    affected: List[Dict[str, Any]],
    available_routes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    proposals = []
    for t in affected:
        delay = float(t.get("delay_minutes") or t.get("estimated_delay_minutes") or 0)
        priority = str(t.get("priority", "")).upper()
        p = {"train_number": t.get("train_number", ""),
             "train_name": t.get("train_name", ""),
             "priority": t.get("priority", "PASSENGER")}

        feasible_diverts = [
            r for r in available_routes
            if r.get("spare_capacity")
            and priority in [x.upper() for x in r.get("compatible_priorities", [])]
        ]
        if delay <= 10:
            proposals.append({**p, "action": "NORMAL", "reasoning": f"Delay {delay} min is within tolerance."})
        elif delay <= 25:
            proposals.append({**p, "action": "HOLD", "minutes_hold": int(delay),
                              "reasoning": f"HOLD {int(delay)} min modulates the train through the block window."})
        elif feasible_diverts:
            route = feasible_diverts[0]
            proposals.append({**p, "action": "DIVERT", "route_id": route["id"],
                              "reasoning": f"DIVERT via {route['name']} (+{route['add_minutes']} min) to clear block window."})
        elif delay <= 30:
            proposals.append({**p, "action": "HOLD", "minutes_hold": int(delay),
                              "reasoning": "No spare-capacity diversion; HOLD is the least-impact option."})
        else:
            proposals.append({**p, "action": "RESCHEDULE",
                              "reasoning": f"High-impact train ({int(delay)} min); propose rescheduling to reduce delay."})
    return proposals


def _llm_propose(section: str, affected: List[Dict[str, Any]], routes: List[Dict[str, Any]], sim: Dict[str, Any], available_routes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    prompt = f"""You are a railway operations regulation assistant. A maintenance block on section "{section}" affects the following trains.

Affected trains:
{affected}

Network-registered alternate routes (you may ONLY reference these route ids for DIVERT):
{routes}

For EACH affected train propose exactly one operational alternative. Action vocabulary:
- "NORMAL": run as scheduled, accept minor delay.
- "HOLD": hold the train; set "minutes_hold" <= 30.
- "DIVERT": divert via one of the listed route ids only.
- "RESCHEDULE": depart later; set "reschedule_to" as HH:MM (advisory only).
- "NO_ACTION": no intervention proposed.

Return JSON: {{"options": [{{"train_number": "...", "train_name": "...", "priority": "...", "action": "...", "minutes_hold": 0, "route_id": null, "reschedule_to": null, "reasoning": "..."}}]}}

Do not invent routes. Do not evaluate safety or feasibility - that is done by a deterministic engine."""

    try:
        text = chat(prompt)
        data = _extract_json(text) or {}
        options = data.get("options", [])
        if isinstance(options, list) and options and all("train_number" in o or "action" in o for o in options):
            return options
    except Exception:
        pass
    return _propose_deterministic(section, affected, available_routes)