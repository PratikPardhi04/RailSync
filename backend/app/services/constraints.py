"""Structured feedback handling.

Officer rejection is NOT a UI event - it is a new planning constraint. This
module converts raw officer text into machine-checkable ReplanningConstraint
objects that deterministic engines (candidate generator, validator) can enforce
instead of hoping the LLM guesses right.
"""
import re
from typing import Any, Dict, List, Optional

from app.schemas.workflow import ReplanningConstraint, hours_minutes_to_mins


def parse_avoid_window(raw: str) -> List[tuple]:
    """Parse "10:00-13:00" or "10:00-13:00,14:00-15:00" into [(start_min, end_min)]."""
    windows = []
    for window in str(raw or "").split(","):
        parts = [p.strip() for p in window.split("-")]
        if len(parts) == 2:
            s = hours_minutes_to_mins(parts[0])
            e = hours_minutes_to_mins(parts[1])
            if e > s:
                windows.append((s, e))
    return windows


def _reason_windows(reason: str) -> List[tuple]:
    """Extract ranges from free-text reasons like 'avoid 10:00 to 13:00'."""
    ranges = []
    matches = re.findall(r"(\d{1,2}(?::\d{2})?)\s*(?:-|to|and|until)\s*(\d{1,2}(?::\d{2})?)", reason)
    for m1, m2 in matches:
        s = hours_minutes_to_mins(m1)
        e = hours_minutes_to_mins(m2)
        if e > s:
            ranges.append((s, e))
    return ranges


def structured_constraints_from_feedback(feedback: Optional[Dict[str, Any]]) -> List[ReplanningConstraint]:
    """Convert officer feedback (rejection_reason / avoid_time / preferred_time /
    additional_constraint) into structured constraints.

    The deterministic candidate generator + validator consume these directly,
    so the LLM is never trusted to (mis)interpret the officer's intent.
    """
    if not feedback:
        return []

    constraints: List[ReplanningConstraint] = []
    windows = list(parse_avoid_window(feedback.get("avoid_time", "")))

    if not windows:
        reason = str(feedback.get("rejection_reason") or "")
        windows = _reason_windows(reason)
        if "after" in reason:
            m = re.search(r"(\d{1,2}:\d{2})", reason)
            if m:
                windows.append((0, hours_minutes_to_mins(m.group(1))))
        elif "before" in reason:
            m = re.search(r"(\d{1,2}:\d{2})", reason)
            if m:
                windows.append((hours_minutes_to_mins(m.group(1)), 24 * 60))

    for s, e in windows:
        constraints.append(ReplanningConstraint(
            type="AVOID_WINDOW",
            start=f"{s // 60:02d}:{s % 60:02d}",
            end=f"{e // 60:02d}:{e % 60:02d}",
            reason=feedback.get("rejection_reason"),
            source="OFFICER",
        ))

    if feedback.get("preferred_time"):
        constraints.append(ReplanningConstraint(
            type="PREFERRED_TIME",
            start=feedback.get("preferred_time"),
            reason=feedback.get("rejection_reason"),
            source="OFFICER",
        ))

    if feedback.get("additional_constraint"):
        constraints.append(ReplanningConstraint(
            type="ADDITIONAL",
            reason=feedback.get("additional_constraint"),
            source="OFFICER",
        ))

    return constraints


def avoids_windows(start_mins: int, end_mins: int, avoid: List[tuple]) -> bool:
    for a_start, a_end in avoid:
        if start_mins < a_end and end_mins > a_start:
            return False  # overlaps an avoid window
    return True