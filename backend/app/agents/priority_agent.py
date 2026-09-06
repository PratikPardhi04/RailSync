import os
import time
from typing import Dict, Any, List

from app.schemas.workflow import PriorityAnalysis

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true" or not os.getenv("GROQ_API_KEY", "")


def run(request: Dict[str, Any], trains: List[Dict[str, Any]]) -> PriorityAnalysis:
    """Priority assessment runs in PARALLEL with Maintenance/Traffic agents.

    It therefore computes its own deterministic traffic overview for the
    preferred window rather than depending on the traffic agent's output.
    """
    start = time.time()

    priority_weights = {"CRITICAL": 10, "HIGH": 8, "MEDIUM": 5, "LOW": 3}
    dept_weights = {"Engineering": 1.0, "S&T": 0.9, "Traction": 0.85}
    type_weights = {"Track Maintenance": 1.0, "Signal Maintenance": 0.95, "Electrical Maintenance": 0.9, "Bridge Inspection": 0.85}

    request_priority = priority_weights.get(request.get("priority", "MEDIUM"), 5)
    dept_score = dept_weights.get(request.get("department", "Engineering"), 0.9)
    type_score = type_weights.get(request.get("maintenance_type", "Track Maintenance"), 0.9)

    affected, total_delay = _impact_overview(request, trains)

    safety_criticality = request_priority * 10
    asset_criticality = type_score * 80
    maintenance_urgency = request_priority * 9
    operational_impact = min(affected * 15, 100)
    passenger_impact = min(total_delay * 2, 100)
    backlog_factor = 70

    priority_score = round(
        (safety_criticality * 0.25 + asset_criticality * 0.15 + maintenance_urgency * 0.20 +
         operational_impact * 0.15 + passenger_impact * 0.10 + backlog_factor * 0.15) * dept_score * type_score, 1
    )

    if priority_score >= 75:
        priority_level = "CRITICAL"
    elif priority_score >= 60:
        priority_level = "HIGH"
    elif priority_score >= 40:
        priority_level = "MEDIUM"
    else:
        priority_level = "LOW"

    reasons = []
    if safety_criticality > 70:
        reasons.append("High safety criticality")
    if affected > 2:
        reasons.append(f"{affected} trains affected")
    if total_delay > 20:
        reasons.append(f"Significant delay ({total_delay} min)")
    if request.get("priority") == "HIGH":
        reasons.append("Engineer-specified high priority")

    return PriorityAnalysis(
        priority_score=priority_score,
        priority_level=priority_level,
        safety_criticality=round(safety_criticality, 1),
        asset_criticality=round(asset_criticality, 1),
        maintenance_urgency=round(maintenance_urgency, 1),
        operational_impact=round(operational_impact, 1),
        passenger_impact=round(passenger_impact, 1),
        reason="; ".join(reasons) if reasons else "Standard priority assessment",
        execution_time=round(time.time() - start, 3),
    )


def _impact_overview(request: Dict[str, Any], trains: List[Dict[str, Any]]) -> tuple:
    """Deterministic pre-window traffic overview (trains in the preferred window)."""
    section = request.get("section", "")
    preferred_start = request.get("preferred_start", "10:00")
    preferred_end = request.get("preferred_end", "14:00")

    affected = 0
    total_delay = 0.0

    for train in trains:
        if section and section.lower() not in train.get("section", "").lower():
            continue
        arr = train.get("arrival_time", "00:00")
        dep = train.get("departure_time", "00:00")
        if _times_overlap(arr, dep, preferred_start, preferred_end):
            affected += 1
            total_delay += _estimate_delay(train, preferred_start, preferred_end)

    return affected, round(total_delay, 1)


def _times_overlap(start1: str, end1: str, start2: str, end2: str) -> bool:
    try:
        s1, e1 = _to_minutes(start1), _to_minutes(end1)
        s2, e2 = _to_minutes(start2), _to_minutes(end2)
        if e1 < s1:
            e1 += 24 * 60
        if e2 < s2:
            e2 += 24 * 60
        return s1 < e2 and s2 < e1
    except Exception:
        return False


def _to_minutes(time_str: str) -> int:
    parts = time_str.strip().split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _estimate_delay(train: Dict[str, Any], block_start: str, block_end: str) -> float:
    train_priority = train.get("priority", "PASSENGER")
    priority_multiplier = {
        "RAJDHANI": 12, "SHATABDI": 10, "VANDE_BHARAT": 11,
        "EXPRESS": 6, "PASSENGER": 4, "FREIGHT": 2,
    }
    base = priority_multiplier.get(train_priority, 4)
    arr = _to_minutes(train.get("arrival_time", "10:00"))
    dep = _to_minutes(train.get("departure_time", "10:05"))
    bs = _to_minutes(block_start)
    be = _to_minutes(block_end)

    if arr >= bs and arr <= be:
        wait = be - arr
        return base + round(wait * 0.15, 1)
    if dep > bs and arr < bs:
        return base + round((dep - bs) * 0.15, 1)
    return base