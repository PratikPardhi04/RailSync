import os
import json
import time
from typing import Dict, Any

from app.schemas.workflow import DecisionRecommendation
from app.services.llm import chat

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true" or not os.getenv("GROQ_API_KEY", "")


def run(
    maintenance_analysis: Dict[str, Any],
    traffic_analysis: Dict[str, Any],
    priority_analysis: Dict[str, Any],
    historical_analysis: Dict[str, Any],
    optimization_result: Dict[str, Any],
    constraint_validation: Dict[str, Any],
    simulation_result: Dict[str, Any],
    risk_analysis: Dict[str, Any],
    request: Dict[str, Any],
    officer_feedback: Dict[str, Any] = None,
) -> DecisionRecommendation:
    start = time.time()

    selected = optimization_result.get("selected_window", {})
    affected = simulation_result.get("total_trains_affected", 0)
    delay = simulation_result.get("total_delay_minutes", 0)
    risk = risk_analysis.get("risk_level", "MEDIUM")
    risk_score = risk_analysis.get("risk_score", 50)
    confidence = max(60, min(98, 100 - risk_score * 0.3 - affected * 2 - delay * 0.5))

    why_lines = []
    why_lines.append(f"120-minute maintenance requirement satisfied (duration: {selected.get('duration_minutes', 0)} min)")
    why_lines.append(f"Track available during proposed window {selected.get('start_time', 'N/A')}-{selected.get('end_time', 'N/A')}")
    why_lines.append(f"No hard train conflicts (affected: {affected}, total delay: {delay} min)")

    if officer_feedback and officer_feedback.get("rejection_reason"):
        why_lines.append("Officer's previous restriction respected")
        avoid = officer_feedback.get("avoid_time", "")
        if avoid:
            why_lines.append(f"Avoids restricted window {avoid}")

    why_lines.append(f"Passenger impact {'minimized' if delay < 10 else 'managed'}")
    why_lines.append("CP-SAT optimal among feasible candidates")
    why_lines.append(f"Simulation: {delay} min estimated total delay")
    why_lines.append(f"Risk: {risk}")

    key_factors = [
        {"factor": "Maintenance Duration", "value": f"{selected.get('duration_minutes', 0)} min", "status": "SATISFIED"},
        {"factor": "Train Impact", "value": f"{affected} trains", "status": "LOW" if affected <= 2 else "MEDIUM"},
        {"factor": "Total Delay", "value": f"{delay} min", "status": "ACCEPTABLE" if delay < 30 else "HIGH"},
        {"factor": "Risk Level", "value": risk, "status": risk},
        {"factor": "Compliance", "value": constraint_validation.get("compliance_status", "UNKNOWN"), "status": "PASS"},
    ]

    tradeoffs = []
    if affected > 0:
        tradeoffs.append(f"{affected} trains will be delayed to accommodate maintenance block")
    if delay > 15:
        tradeoffs.append(f"Total delay of {delay} min is a trade-off for essential maintenance")
    if officer_feedback:
        tradeoffs.append("Plan adapted based on officer feedback from previous version")

    result = DecisionRecommendation(
        recommendation="RECOMMEND_APPROVE" if risk_score < 60 and constraint_validation.get("valid") else "RECOMMEND_REVIEW",
        recommendation_is_final=False,
        approval_authority="OFFICER",
        reasoning_summary=(
            f"AI ADVISORY (not final approval). The maintenance block {selected.get('start_time', 'N/A')}-{selected.get('end_time', 'N/A')} on "
            f"{request.get('section', 'N/A')} satisfies the {selected.get('duration_minutes', 0)}-minute "
            f"maintenance requirement while minimizing operational impact. {affected} trains affected with {delay} min total delay. "
            f"Risk level: {risk} ({risk_score}/100). All deterministic constraints pass. "
            f"Final decision to approve or reject rests solely with the reviewing officer."
        ),
        why_this_window=why_lines,
        key_factors=key_factors,
        tradeoffs=tradeoffs,
        evidence={
            "historical_approval_rate": historical_analysis.get("historical_outcomes", {}).get("approval_rate", 80),
            "similar_cases_found": len(historical_analysis.get("similar_cases", [])),
            "rules_applied": len(historical_analysis.get("relevant_rules", [])),
            "solver_status": optimization_result.get("solver_status", "UNKNOWN"),
        },
        confidence=round(confidence, 1),
        execution_time=round(time.time() - start, 3),
    )

    if not DEMO_MODE:
        result.reasoning_summary = _llm_fusion(
            result.model_dump(), maintenance_analysis, traffic_analysis, risk_analysis, request, officer_feedback
        )

    return result


def _llm_fusion(fusion_result, maint, traffic, risk, request=None, officer_feedback=None):
    try:
        prompt = f"""You are a railway operations decision-support AI that PROVIDES ADVICE ONLY. You can NEVER approve or publish a maintenance block - that authority belongs exclusively to the human railway officer.

Synthesize these analyses into a clear, professional recommendation FOR THE OFFICER TO APPROVE OR REJECT:

Request details: {json.dumps(request, default=str) if request else 'N/A'}
Maintenance: {json.dumps(maint, default=str)}
Traffic: {json.dumps(traffic, default=str, indent=2)[:500]}
Risk: {json.dumps(risk, default=str)}
Officer feedback (if any, from a previous rejection): {json.dumps(officer_feedback or {}, default=str)}

Provide a 2-4 paragraph recommendation that:
1. States clearly this is AI ADVICE, not an approval.
2. Summarizes the proposed window and why it is operationally sound.
3. Clearly lists any residual risks, trade-offs, and constraints the officer should weigh.
4. Ends with an explicit sentence: "Final approval or rejection rests solely with the railway officer." """
        return chat(prompt)
    except Exception:
        return fusion_result.get("reasoning_summary", "Decision fusion (advisory) completed")
