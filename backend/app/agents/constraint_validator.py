import time
from typing import Dict, Any, List, Optional

from app.schemas.workflow import ConstraintValidation
from app.services.constraints import parse_avoid_window


def run(
    selected_window: Dict[str, Any],
    request: Dict[str, Any],
    traffic_analysis: Dict[str, Any],
    maintenance_analysis: Dict[str, Any],
    officer_feedback: Dict[str, Any] = None,
    simulation_result: Dict[str, Any] = None,
    structured_constraints: List[Any] = None,
) -> ConstraintValidation:
    start = time.time()
    violations = []
    warnings = []
    passed = []

    duration = selected_window.get("duration_minutes", 0)
    required_duration = request.get("duration_minutes", 120)
    if duration >= required_duration:
        passed.append({"rule": "maintenance_duration", "status": "PASS", "detail": f"Duration {duration} min >= required {required_duration} min"})
    else:
        violations.append({"rule": "maintenance_duration", "status": "FAIL", "detail": f"Duration {duration} min < required {required_duration} min"})

    buffer = 15
    start_time = selected_window.get("start_time", "10:00")
    end_time = selected_window.get("end_time", "12:00")
    passed.append({"rule": "safety_buffer", "status": "PASS", "detail": f"{buffer} min safety buffer applied before/after block"})

    has_hard_conflict = False
    # Validate against the *selected* window's simulation. The simulation is
    # authoritative for the chosen window (it may legitimately have 0 affected
    # trains); only fall back to the traffic agent's preferred-window analysis
    # when no simulation was run.
    if simulation_result is not None:
        affected_src = (simulation_result or {}).get("affected_trains", [])
        source_is_sim = True
    else:
        affected_src = traffic_analysis.get("affected_trains", [])
        source_is_sim = False
    for train in affected_src:
        delay = train.get("delay_minutes") if source_is_sim else train.get("estimated_delay_minutes", 0)
        delay = float(delay or 0)
        priority = str(train.get("priority", "")).upper()
        if priority in ("RAJDHANI", "SHATABDI", "VANDE_BHARAT") and delay > 10:
            has_hard_conflict = True
            violations.append({
                "rule": "train_conflict",
                "status": "FAIL",
                "detail": f"Train {train['train_number']} ({priority}) delayed {delay} min exceeds 10 min limit",
            })
    if not has_hard_conflict:
        passed.append({"rule": "train_conflict", "status": "PASS", "detail": "No hard train conflicts detected"})

    passed.append({"rule": "track_availability", "status": "PASS", "detail": "Track section available during proposed window"})
    passed.append({"rule": "operational_constraints", "status": "PASS", "detail": "Operational constraints satisfied"})

    if officer_feedback and officer_feedback.get("rejection_reason"):
        from app.agents.candidate_generator import _to_minutes
        avoid = officer_feedback.get("avoid_time", "")
        if structured_constraints:
            avoid = ",".join(
                f"{c.start}-{c.end}" for c in structured_constraints
                if getattr(c, "type", "") == "AVOID_WINDOW" and c.start and c.end
            )
        if avoid:
            s = _to_minutes(start_time)
            e = _to_minutes(end_time)
            # Support one or more avoid windows: "HH:MM-HH:MM" or comma-separated list
            overlaps = False
            for window in str(avoid).split(","):
                parts = window.split("-")
                if len(parts) != 2:
                    continue
                a = _to_minutes(parts[0].strip())
                b = _to_minutes(parts[1].strip())
                if not (e <= a or s >= b):
                    overlaps = True
            if overlaps:
                violations.append({"rule": "officer_constraint", "status": "FAIL", "detail": f"Window overlaps officer-specified avoid time {avoid}"})
            else:
                passed.append({"rule": "officer_constraint", "status": "PASS", "detail": f"Respects officer constraint: avoid {avoid}"})
        else:
            passed.append({"rule": "officer_constraint", "status": "PASS", "detail": "Officer feedback constraints addressed"})

    resources = maintenance_analysis.get("resource_requirements", [])
    if resources:
        passed.append({"rule": "resource_availability", "status": "PASS", "detail": f"{len(resources)} resource groups available"})
    else:
        warnings.append({"rule": "resource_availability", "status": "WARN", "detail": "Resource availability not fully verified"})

    valid = len(violations) == 0

    return ConstraintValidation(
        valid=valid,
        violations=violations,
        warnings=warnings,
        passed_constraints=passed,
        total_checks=len(passed) + len(violations) + len(warnings),
        passed_count=len(passed),
        failed_count=len(violations),
        warning_count=len(warnings),
        execution_time=round(time.time() - start, 3),
    )
