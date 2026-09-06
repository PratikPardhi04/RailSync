import os
import json
import time
from typing import Dict, Any, List

from app.schemas.workflow import TrafficAnalysis

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true" or not os.getenv("GROQ_API_KEY", "")


def run(request: Dict[str, Any], trains: List[Dict[str, Any]]) -> TrafficAnalysis:
    start = time.time()
    section = request.get("section", "")
    preferred_start = request.get("preferred_start", "10:00")
    preferred_end = request.get("preferred_end", "14:00")
    duration = request.get("duration_minutes", 120)

    affected = []
    conflict_windows = []

    for train in trains:
        if section and section.lower() in train.get("section", "").lower():
            arr = train.get("arrival_time", "00:00")
            dep = train.get("departure_time", "00:00")
            if _times_overlap(arr, dep, preferred_start, preferred_end):
                delay = _estimate_delay(train, preferred_start, preferred_end)
                affected.append({
                    "train_number": train["train_number"],
                    "train_name": train["train_name"],
                    "train_type": train["train_type"],
                    "priority": train.get("priority", "MEDIUM"),
                    "arrival_time": arr,
                    "departure_time": dep,
                    "estimated_delay_minutes": delay,
                    "impact": "HIGH" if train.get("priority") in ("RAJDHANI", "SHATABDI", "VANDE_BHARAT") else "MEDIUM" if train.get("priority") == "EXPRESS" else "LOW",
                })
                conflict_windows.append({"start": arr, "end": dep, "train": train["train_number"]})

    total_delay = sum(a["estimated_delay_minutes"] for a in affected)
    density = len(trains)

    result = TrafficAnalysis(
        affected_trains=affected,
        conflict_windows=conflict_windows,
        traffic_density=density,
        total_affected=len(affected),
        total_estimated_delay=round(total_delay, 1),
        estimated_impact="HIGH" if len(affected) > 3 else "MEDIUM" if len(affected) > 1 else "LOW",
        section=section,
        analysis_window=f"{preferred_start} - {preferred_end}",
        summary=(
            f"Traffic analysis for section {section}: {len(affected)} trains affected in the "
            f"proposed window {preferred_start}-{preferred_end}. Total estimated delay: {round(total_delay, 1)} min. "
            f"Traffic density: {density} trains on section."
        ),
        execution_time=round(time.time() - start, 3),
    )

    if not DEMO_MODE:
        result.summary = _llm_enhance(result.model_dump())

    return result


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
    # Same congestion-aware model as the simulator so candidate scoring matches
    # the final deterministic simulation for busy corridors.
    priority_multiplier = {
        "RAJDHANI": 15, "SHATABDI": 13, "VANDE_BHARAT": 14, "SUPERFAST": 11,
        "EXPRESS": 10, "PASSENGER": 8, "FREIGHT": 6,
    }
    base = priority_multiplier.get(train.get("priority", "PASSENGER"), 8)
    arr = _to_minutes(train.get("arrival_time", "10:00"))
    dep = _to_minutes(train.get("departure_time", "10:05"))
    if dep < arr:
        dep += 24 * 60
    bs = _to_minutes(block_start)
    be = _to_minutes(block_end)

    if arr >= bs and arr < be:
        wait = be - arr
    elif arr < bs and dep > bs:
        wait = dep - bs
    else:
        wait = 0

    if wait <= 0:
        return base
    return base + round(wait * 0.4, 1)


def _llm_enhance(result: Dict[str, Any]) -> str:
    try:
        from langchain_groq import ChatGroq
        llm = ChatGroq(groq_api_key=os.getenv("GROQ_API_KEY"), model="qwen/qwen3.8-27b")
        prompt = f"""Analyze this railway traffic impact and provide a brief professional summary:
{json.dumps(result, indent=2, default=str)}"""
        response = llm.invoke(prompt)
        return response.content
    except Exception:
        return result.get("summary", "Traffic analysis completed")
