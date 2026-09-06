import os
import json
import time
from typing import Dict, Any, List, Optional

from app.schemas.workflow import HistoricalAnalysis

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true" or not os.getenv("GROQ_API_KEY", "")


def run(request: Dict[str, Any], rag_store=None) -> HistoricalAnalysis:
    start = time.time()
    section = request.get("section", "")
    maint_type = request.get("maintenance_type", "")
    duration = request.get("duration_minutes", 120)

    similar_cases = [
        {
            "case_id": "HIST-2025-0142",
            "section": section or "Shivajinagar - Khadki",
            "maintenance_type": maint_type or "Track Maintenance",
            "duration": duration,
            "proposed_window": "09:30 - 11:30",
            "outcome": "APPROVED",
            "affected_trains": 2,
            "delay_minutes": 15,
            "date": "2025-08-15",
            "similarity_score": 0.92,
        },
        {
            "case_id": "HIST-2025-0098",
            "section": section or "Shivajinagar - Khadki",
            "maintenance_type": "Signal Maintenance",
            "duration": 90,
            "proposed_window": "14:00 - 15:30",
            "outcome": "APPROVED",
            "affected_trains": 1,
            "delay_minutes": 5,
            "date": "2025-07-22",
            "similarity_score": 0.85,
        },
        {
            "case_id": "HIST-2025-0203",
            "section": "Pune - Lonavala",
            "maintenance_type": maint_type or "Track Maintenance",
            "duration": 180,
            "proposed_window": "22:00 - 01:00",
            "outcome": "REJECTED_V1_APPROVED_V2",
            "affected_trains": 4,
            "delay_minutes": 45,
            "date": "2025-09-01",
            "similarity_score": 0.78,
        },
    ]

    rules = [
        {
            "rule_id": "IRPWM-4.2.1",
            "title": "Track Maintenance Block Requirements",
            "source": "IRPWM (Prototype Reference)",
            "content": "Minimum 120 minutes required for track maintenance. Safety buffer of 15 minutes before and after block mandatory.",
            "relevance": 0.95,
        },
        {
            "rule_id": "GSR-7.3",
            "title": "Train Priority During Maintenance",
            "source": "G&SR (Prototype Reference)",
            "content": "Rajdhani and Shatabdi trains must not be delayed more than 10 minutes during planned maintenance blocks.",
            "relevance": 0.88,
        },
        {
            "rule_id": "SWR-12.1",
            "title": "Section Handover Protocol",
            "source": "SWR (Prototype Reference)",
            "content": "Section must be formally handed over to maintenance team and verified clear before block starts.",
            "relevance": 0.82,
        },
    ]

    recommendations = [
        "Based on historical data, 09:00-11:00 windows have 85% approval rate for track maintenance",
        "Freight-heavy windows (22:00-06:00) show lower passenger impact",
        "Previous rejection at this section was due to passenger train conflict - avoid 10:00-13:00",
    ]

    if rag_store:
        try:
            rag_results = rag_store.search(f"{maint_type} {section} maintenance", k=3)
            if rag_results:
                rules.extend([{"rule_id": f"RAG-{i}", "title": r.get("title", "Knowledge"), "source": "RAG Knowledge Base", "content": r.get("content", ""), "relevance": r.get("score", 0.7)} for i, r in enumerate(rag_results)])
        except Exception:
            pass

    return HistoricalAnalysis(
        similar_cases=similar_cases,
        relevant_rules=rules,
        recommendations=recommendations,
        historical_outcomes={"approved": 12, "rejected": 3, "replanned": 5, "approval_rate": 80.0},
        summary=(
            f"Historical analysis: Found {len(similar_cases)} similar cases. "
            f"{len(rules)} relevant rules retrieved. Historical approval rate: 80%. "
            f"Key recommendation: Avoid peak passenger hours for track maintenance."
        ),
        execution_time=round(time.time() - start, 3),
    )
