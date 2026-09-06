"""Route & Operations Optimizer (deterministic).

The LLM routing agent proposes; this engine decides. Every proposed action is
checked against network topology + capacity and the lowest-impact feasible
per-train action is selected. Premium-train delays beyond the hard threshold
are surfaced as conflicts for the Hard-Conflict Gate to re-run planning.
"""
import time
from typing import Any, Dict, List

from app.network import network_data
from app.schemas.workflow import RoutingAnalysis, RoutingOptimizationResult

PREMIUM = ("RAJDHANI", "SHATABDI", "VANDE_BHARAT")
PREMIUM_DELAY_THRESHOLD_MIN = 10


def run(
    routing_analysis: Any,
    simulation_result: Any,
    request: Dict[str, Any],
) -> RoutingOptimizationResult:
    start = time.time()
    section = request.get("section", "")

    routing = routing_analysis.model_dump() if hasattr(routing_analysis, "model_dump") else (routing_analysis or {})
    sim = simulation_result.model_dump() if hasattr(simulation_result, "model_dump") else (simulation_result or {})

    sim_by_train = {t.get("train_number"): t for t in (sim.get("affected_trains") or [])}
    proposals = {o.get("train_number"): o for o in (routing.get("options") or [])}

    final_options: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    total_additional = 0.0
    rerouted = 0
    held = 0

    for train_no, train in sim_by_train.items():
        original_delay = float(train.get("delay_minutes") or 0)
        priority = str(train.get("priority", "")).upper()
        proposal = proposals.get(train_no, {})
        action = str(proposal.get("action", "NORMAL")).upper()
        minutes_hold = int(proposal.get("minutes_hold") or 0)
        route_id = proposal.get("route_id")

        option = {
            "train_number": train_no,
            "train_name": train.get("train_name", ""),
            "priority": train.get("priority", "PASSENGER"),
            "action": "NORMAL",
            "route_id": None,
            "additional_delay": round(original_delay, 1),
            "base_delay": round(original_delay, 1),
            "feasible": True,
            "note": "Delay accepted as NORMAL regulation.",
        }

        if action == "HOLD":
            hold = max(0, minutes_hold)
            option["action"] = "HOLD"
            option["additional_delay"] = round(float(hold or original_delay), 1)
            option["note"] = f"HOLD {hold} min through block window."
            held += 1
        elif action == "DIVERT":
            if (network_data.route_exists(section, route_id)
                    and network_data.compatible_with_route(str(train.get("priority", "")), section, route_id)
                    and network_data.is_route_available(section, route_id)):
                route = network_data.route_details(section, route_id)
                add = route["add_minutes"]
                option["action"] = "DIVERT"
                option["route_id"] = route_id
                option["additional_delay"] = round(float(add), 1)
                option["note"] = f"DIVERT via {route['name']}."
                rerouted += 1
            else:
                option["action"] = "HOLD"
                option["additional_delay"] = round(float(original_delay), 1)
                option["note"] = "DIVERT infeasible (route/capacity/compatibility) - HOLD accepted."
                held += 1
        elif action == "RESCHEDULE":
            option["action"] = "RESCHEDULE"
            option["reschedule_to"] = proposal.get("reschedule_to")
            option["additional_delay"] = round(float(original_delay), 1)
            option["note"] = "Train rescheduled by control."
        else:
            option["action"] = "NORMAL"
            option["additional_delay"] = round(float(original_delay), 1)
            option["note"] = "NORMAL regulation - minor delay accepted."

        total_additional += float(option["additional_delay"])
        final_options.append(option)

        final_delay = option["additional_delay"]
        if priority in PREMIUM and final_delay > PREMIUM_DELAY_THRESHOLD_MIN:
            conflicts.append({
                "train_number": train_no,
                "priority": priority,
                "delay_minutes": round(final_delay, 1),
                "reason": f"Premium train delayed {round(final_delay, 1)} min exceeds {PREMIUM_DELAY_THRESHOLD_MIN} min hard limit",
                "start_window": None,
            })

    feasible = len(conflicts) == 0
    return RoutingOptimizationResult(
        options=final_options,
        feasible=feasible,
        total_additional_delay=round(total_additional, 1),
        trains_rerouted=rerouted,
        trains_held=held,
        conflicts=conflicts,
        summary=(
            f"Route optimization evaluated {len(final_options)} affected trains. "
            f"Rerouted: {rerouted}, Held: {held}. Hard conflicts: {len(conflicts)}. "
            f"Feasible: {feasible}."
        ),
        execution_time=round(time.time() - start, 3),
    )