import os
import json
import time
from typing import Dict, Any, List

from app.schemas.workflow import MaintenanceAnalysis

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true" or not os.getenv("GROQ_API_KEY", "")


def run(request: Dict[str, Any]) -> MaintenanceAnalysis:
    start = time.time()
    duration = request.get("duration_minutes", 120)
    maint_type = request.get("maintenance_type", "Track Maintenance")
    department = request.get("department", "Engineering")
    priority = request.get("priority", "HIGH")
    section = request.get("section", "Unknown")

    resource_map = {
        "Track Maintenance": ["Track Gang (12 personnel)", "Rail Cutting Machine", "Tamping Machine", "Leveling Instrument", "Ballast Regulator"],
        "Signal Maintenance": ["Signal Technician (4)", "Signal Testing Kit", "Cable Testing Equipment", "Replacement Signal Heads"],
        "Electrical Maintenance": ["Electrical Team (6)", "Insulation Tester", "Load Testing Equipment", "Safety Gear"],
        "Bridge Inspection": ["Structural Engineers (3)", "NDT Equipment", "Access Equipment", "Safety Harnesses"],
    }

    constraints_map = {
        "Track Maintenance": [
            "Track must be de-energized if OHE present",
            "Minimum 15 min safety buffer before/after block",
            "Ballast work requires crane access",
            "Section to be handed over to Engineering dept",
        ],
        "Signal Maintenance": [
            "Adjacent signals must be manually controlled",
            "Level crossing gates must be manned",
            "DCS backup required during maintenance",
        ],
        "Electrical Maintenance": [
            "OHE must be isolated and earthed",
            "Minimum 2 earth connections required",
            "Live line work prohibited during block",
        ],
        "Bridge Inspection": [
            "Traffic diversions required",
            "NDT during daylight hours only",
            "Minimum 2 personnel for confined spaces",
        ],
    }

    resources = resource_map.get(maint_type, ["General maintenance crew (8)", "Standard tool kit"])
    constraints = constraints_map.get(maint_type, ["Standard safety protocols apply"])

    result = MaintenanceAnalysis(
        maintenance_duration=duration,
        resource_requirements=resources,
        priority=priority,
        maintenance_constraints=constraints,
        section=section,
        summary=(
            f"{maint_type} for {department} department on section {section}. "
            f"Duration: {duration} min. Resources required: {len(resources)} equipment groups. "
            f"Safety constraints: {len(constraints)}. Priority: {priority}."
        ),
        urgency="HIGH" if priority in ("HIGH", "CRITICAL") else "MEDIUM",
        preferred_start=request.get("preferred_start", "10:00"),
        preferred_end=request.get("preferred_end", "14:00"),
        requested_date=request.get("requested_date", ""),
        execution_time=round(time.time() - start, 3),
    )

    if not DEMO_MODE:
        result.summary = _llm_enhance_summary(result.model_dump())
        result.llm_enhanced = True

    return result


def _llm_enhance_summary(analysis: Dict[str, Any]) -> str:
    try:
        from langchain_groq import ChatGroq
        llm = ChatGroq(groq_api_key=os.getenv("GROQ_API_KEY"), model="qwen/qwen3.8-27b")
        prompt = f"""You are a railway maintenance planning AI. Analyze this maintenance request and provide a concise expert summary:
{json.dumps(analysis, indent=2)}
Provide a 2-3 sentence professional summary for railway operations."""
        response = llm.invoke(prompt)
        return response.content
    except Exception:
        return analysis.get("summary", "Maintenance analysis completed")
