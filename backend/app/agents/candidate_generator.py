import os
import time
from typing import Dict, Any, List, Optional

from app.schemas.workflow import CandidateGenerationResult
from app.services.constraints import parse_avoid_window, structured_constraints_from_feedback

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true" or not os.getenv("GROQ_API_KEY", "")


def run(
    request: Dict[str, Any],
    maintenance_analysis: Dict[str, Any],
    traffic_analysis: Dict[str, Any],
    historical_analysis: Dict[str, Any],
    officer_feedback: Dict[str, Any] = None,
    structured_constraints: Optional[List[Any]] = None,
) -> CandidateGenerationResult:
    """Generate candidate windows.

    The LLM (or deterministic rule engine here) only PROPOSES candidate windows.
    It does NOT decide which candidate is optimal - CP-SAT does that.
    """
    start = time.time()

    preferred_start = request.get("preferred_start", "10:00")
    preferred_end = request.get("preferred_end", "14:00")
    duration = request.get("duration_minutes", 120)
    safety_buffer = 15

    ps_min = _to_minutes(preferred_start)
    pe_min = _to_minutes(preferred_end)

    # Structured constraints are authoritative (derived from officer feedback).
    if structured_constraints:
        avoid_windows = [
            (a, b)
            for c in structured_constraints
            if getattr(c, "type", "") == "AVOID_WINDOW" and c.start and c.end
            for a, b in parse_avoid_window(f"{c.start}-{c.end}")
        ]
    elif officer_feedback:
        avoid_windows = parse_avoid_window(officer_feedback.get("avoid_time", ""))
        if not avoid_windows:
            reason = str(officer_feedback.get("rejection_reason") or "").lower()
            import re
            it_matches = re.findall(r'(\d{1,2}(?::\d{2})?)\s*(?:-|to|and|until)\s*(\d{1,2}(?::\d{2})?)', reason)
            for m1, m2 in it_matches:
                avoid_windows.append((_to_minutes(m1), _to_minutes(m2)))
            if "after" in reason:
                time_match = re.search(r'(\d{1,2}:\d{2})', officer_feedback.get("rejection_reason", ""))
                if time_match:
                    avoid_windows.append((ps_min, _to_minutes(time_match.group(1))))
            elif "before" in reason:
                time_match = re.search(r'(\d{1,2}:\d{2})', officer_feedback.get("rejection_reason", ""))
                if time_match:
                    avoid_windows.append((_to_minutes(time_match.group(1)), 24 * 60))
    else:
        avoid_windows = []

    candidates = []
    step = 30
    # Start from preferred start, but if there's an avoid window that blocks the
    # preferred range, extend beyond the preferred end so a feasible window can be found
    search_start = ps_min
    search_end = pe_min

    if avoid_windows:
        # If avoid windows overlap the preferred range, extend the search window
        # beyond the latest avoid end so a feasible window can still be found.
        max_avoid_end = max((aw[1] for aw in avoid_windows), default=0)
        # An avoid window blocks feasible options if it covers most of the preferred range
        search_end = max(pe_min, max_avoid_end + 150)
        # Also try starting a bit earlier if preferred start is blocked
        min_avoid_start = min((aw[0] for aw in avoid_windows), default=0)
        if min_avoid_start <= ps_min and max_avoid_end >= ps_min:
            search_start = max(0, max_avoid_end)

    current = search_start
    while current + duration <= search_end:
        end = current + duration
        overlaps_avoid = False
        for aw_start, aw_end in avoid_windows:
            if current < aw_end and end > aw_start:
                overlaps_avoid = True
                break

        if not overlaps_avoid:
            affected_count = _count_affected_trains(current, end, traffic_analysis)
            delay = _estimate_total_delay(current, end, traffic_analysis)
            score = _calculate_score(current, end, ps_min, pe_min, affected_count, delay)

            candidates.append({
                "start_time": _to_time_str(current),
                "end_time": _to_time_str(end),
                "duration_minutes": duration,
                "affected_trains": affected_count,
                "estimated_delay_minutes": round(delay, 1),
                "score": round(score, 2),
                "avoids_officer_constraint": bool(avoid_windows),
                "within_preferred": end <= pe_min,
            })
        current += step

    candidates.sort(key=lambda x: x["score"], reverse=True)

    top_n = min(6, len(candidates))

    return CandidateGenerationResult(
        candidates=candidates[:top_n] if candidates else [],
        total_evaluated=len(candidates),
        constraints_applied={
            "duration": duration,
            "safety_buffer": safety_buffer,
            "preferred_window": f"{preferred_start} - {preferred_end}",
            "avoid_windows": [f"{_to_time_str(a)}-{_to_time_str(b)}" for a, b in avoid_windows] if avoid_windows else [],
            "officer_feedback_applied": bool(officer_feedback and officer_feedback.get("rejection_reason")) or bool(structured_constraints),
        },
        summary=(
            f"Generated {len(candidates[:top_n])} candidate windows from {len(candidates)} evaluated. "
            f"Top candidate: {candidates[0]['start_time']}-{candidates[0]['end_time']} "
            f"with score {candidates[0]['score']}" if candidates else
            "No feasible candidate windows found within constraints."
        ),
        execution_time=round(time.time() - start, 3),
    )


def _to_minutes(time_str: str) -> int:
    parts = time_str.strip().split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _to_time_str(minutes: int) -> str:
    h = (minutes // 60) % 24
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def _count_affected_trains(start_min: int, end_min: int, traffic: Dict[str, Any]) -> int:
    count = 0
    for train in traffic.get("affected_trains", []):
        arr = _to_minutes(train.get("arrival_time", "00:00"))
        dep = _to_minutes(train.get("departure_time", "00:00"))
        if dep < arr:
            dep += 24 * 60
        if arr < end_min and dep > start_min:
            count += 1
    return count


def _estimate_total_delay(start_min: int, end_min: int, traffic: Dict[str, Any]) -> float:
    total = 0
    for train in traffic.get("affected_trains", []):
        arr = _to_minutes(train.get("arrival_time", "00:00"))
        dep = _to_minutes(train.get("departure_time", "00:00"))
        if dep < arr:
            dep += 24 * 60
        if arr < end_min and dep > start_min:
            total += train.get("estimated_delay_minutes", 5)
    return total


def _calculate_score(start: int, end: int, pref_start: int, pref_end: int, affected: int, delay: float) -> float:
    deviation = abs(start - pref_start) + abs(end - pref_end)
    deviation_penalty = min(deviation / 120, 1.0) * 20
    affected_penalty = affected * 5
    delay_penalty = min(delay / 60, 1.0) * 15
    score = 100 - deviation_penalty - affected_penalty - delay_penalty
    return max(0, min(100, score))
