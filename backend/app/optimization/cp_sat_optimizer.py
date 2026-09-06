import os
import time
import json
from typing import Dict, Any, List, Optional, Tuple

from app.schemas.workflow import OptimizationResult

try:
    from ortools.sat.python import cp_model
    HAS_ORTOOLS = True
except ImportError:
    HAS_ORTOOLS = False


def run(
    candidates: List[Dict[str, Any]],
    request: Dict[str, Any],
    traffic_analysis: Dict[str, Any],
    constraints: Dict[str, Any] = None,
) -> Dict[str, Any]:
    start = time.time()

    if not HAS_ORTOOLS:
        return _fallback_optimizer(candidates, request, traffic_analysis)

    if not candidates:
        return OptimizationResult(
            feasible=False,
            selected_window=None,
            objective_score=0,
            violations=["No candidate windows available"],
            execution_time=round(time.time() - start, 3),
        )

    model = cp_model.CpModel()
    n = len(candidates)
    selected = [model.NewBoolVar(f"select_{i}") for i in range(n)]

    model.Add(sum(selected) == 1)

    duration = request.get("duration_minutes", 120)
    for i, c in enumerate(candidates):
        if c["duration_minutes"] != duration:
            model.Add(selected[i] == 0)

    affected_trains = []
    for c in candidates:
        affected_trains.append(c.get("affected_trains", 0))
    delays = []
    for c in candidates:
        delays.append(c.get("estimated_delay_minutes", 0))
    scores = []
    for c in candidates:
        scores.append(int(c.get("score", 0) * 100))

    model.Maximize(
        sum(selected[i] * scores[i] for i in range(n))
        - sum(selected[i] * affected_trains[i] * 500 for i in range(n))
        - sum(selected[i] * int(delays[i] * 100) for i in range(n))
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.num_workers = 1
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected_idx = None
        for i in range(n):
            if solver.Value(selected[i]) == 1:
                selected_idx = i
                break

        if selected_idx is not None:
            selected_candidate = candidates[selected_idx]
            objective_value = solver.ObjectiveValue()

            return OptimizationResult(
                feasible=True,
                selected_window={
                    "start_time": selected_candidate["start_time"],
                    "end_time": selected_candidate["end_time"],
                    "duration_minutes": selected_candidate["duration_minutes"],
                },
                objective_score=round(objective_value / 100, 2),
                affected_trains=selected_candidate.get("affected_trains", 0),
                estimated_delay_minutes=selected_candidate.get("estimated_delay_minutes", 0),
                all_candidates_scores=[
                    {"start": c["start_time"], "end": c["end_time"], "score": c["score"]}
                    for c in candidates
                ],
                constraints_satisfied=True,
                solver_status="OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
                execution_time=round(time.time() - start, 3),
            )

    return OptimizationResult(
        feasible=False,
        selected_window=None,
        objective_score=0,
        violations=["CP-SAT could not find a feasible solution within time limit"],
        solver_status="INFEASIBLE",
        execution_time=round(time.time() - start, 3),
    )


def _fallback_optimizer(candidates, request, traffic_analysis):
    start = time.time()
    if not candidates:
        return OptimizationResult(feasible=False, selected_window=None, objective_score=0, violations=["No candidates"], execution_time=round(time.time() - start, 3))

    best = max(candidates, key=lambda c: c.get("score", 0))
    return OptimizationResult(
        feasible=True,
        selected_window={
            "start_time": best["start_time"],
            "end_time": best["end_time"],
            "duration_minutes": best["duration_minutes"],
        },
        objective_score=best.get("score", 0),
        affected_trains=best.get("affected_trains", 0),
        estimated_delay_minutes=best.get("estimated_delay_minutes", 0),
        constraints_satisfied=True,
        solver_status="FALLBACK_GREEDY",
        execution_time=round(time.time() - start, 3),
    )
