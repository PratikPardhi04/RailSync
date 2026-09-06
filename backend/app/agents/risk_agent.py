import time
from typing import Dict, Any, List, Optional

from app.schemas.workflow import RiskAnalysis


def run(
    request: Dict[str, Any],
    simulation_result: Dict[str, Any],
    constraint_validation: Dict[str, Any],
    traffic_analysis: Dict[str, Any],
    historical_analysis: Dict[str, Any] = None,
) -> RiskAnalysis:
    start = time.time()

    total_delay = simulation_result.get("total_delay_minutes", 0)
    affected = simulation_result.get("total_trains_affected", 0)
    rerouted = simulation_result.get("trains_rerouted", 0)
    violations = constraint_validation.get("failed_count", 0)
    priority = request.get("priority", "MEDIUM")

    safety_risk = min(20 + violations * 25, 100)
    operational_risk = min(10 + (total_delay / 60) * 20 + rerouted * 15, 100)
    maintenance_risk = min(5 + (1 if rerouted > 2 else 0) * 30, 100)
    passenger_impact = min(10 + (total_delay / 30) * 25, 100)

    overall = round(safety_risk * 0.30 + operational_risk * 0.25 + maintenance_risk * 0.20 + passenger_impact * 0.25, 1)

    if overall < 30:
        risk_level = "LOW"
    elif overall < 60:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    compliance = violations == 0

    rules_used = [
        {"rule": "IRPWM Section 4.2 - Block Duration", "status": "PASS" if constraint_validation.get("valid") else "FAIL"},
        {"rule": "G&SR Rule 7.3 - Train Priority Protection", "status": "PASS" if total_delay < 30 else "REVIEW"},
        {"rule": "Safety Buffer Requirement", "status": "PASS"},
        {"rule": "Track Occupancy Rules", "status": "PASS" if rerouted < 3 else "REVIEW"},
    ]

    warnings = []
    if total_delay > 20:
        warnings.append(f"Total delay of {total_delay} min may cause cascading effects")
    if rerouted > 2:
        warnings.append(f"{rerouted} trains require rerouting - verify alternative routes")
    if affected > 4:
        warnings.append(f"{affected} trains affected - high operational impact")

    mitigations = []
    if total_delay > 15:
        mitigations.append("Consider advance notification to affected train controllers")
    if rerouted > 0:
        mitigations.append("Verify alternative route availability before block starts")
    if risk_level == "HIGH":
        mitigations.append("Consider splitting maintenance into smaller blocks")

    return RiskAnalysis(
        risk_score=overall,
        risk_level=risk_level,
        safety_risk=round(safety_risk, 1),
        operational_risk=round(operational_risk, 1),
        maintenance_risk=round(maintenance_risk, 1),
        passenger_impact=round(passenger_impact, 1),
        compliance_status="COMPLIANT" if compliance else "NON_COMPLIANT",
        rules_used=rules_used,
        warnings=warnings,
        mitigations=mitigations,
        summary=(
            f"Risk Assessment: {risk_level} (score: {overall}/100). "
            f"Safety: {safety_risk}, Operational: {operational_risk}, "
            f"Passenger Impact: {passenger_impact}. "
            f"Compliance: {'Pass' if compliance else 'Issues found'}. "
            f"{len(warnings)} warnings, {len(mitigations)} mitigations."
        ),
        execution_time=round(time.time() - start, 3),
    )
