import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.graph.workflow import run_workflow
from app.database.connection import SessionLocal, init_db
from app.models.models import Train

init_db()
db = SessionLocal()
train_data = [
    {
        "train_number": t.train_number,
        "train_name": t.train_name,
        "train_type": t.train_type,
        "priority": t.priority,
        "origin": t.origin,
        "destination": t.destination,
        "section": t.section,
        "arrival_time": t.arrival_time,
        "departure_time": t.departure_time,
        "average_speed": t.average_speed,
    }
    for t in db.query(Train).all()
]
db.close()

req = {
    "id": 999,
    "department": "Engineering",
    "maintenance_type": "Track Maintenance",
    "location": "Pune Division",
    "section": "Shivajinagar - Khadki",
    "requested_date": "2026-09-04",
    "preferred_start": "10:00",
    "preferred_end": "14:00",
    "duration_minutes": 120,
    "priority": "HIGH",
    "description": "Test"
}

print("=== VERSION 1 ===")
result = run_workflow(req, train_data, 1, None)
print("Status:", result.get("status"))
if result.get("status") == "REPORT_READY":
    print("Window:", result["selected_window"])
    sim = result["simulation_result"]
    print("Affected:", sim["total_trains_affected"])
    print("Delay:", sim["total_delay_minutes"])
    print("Risk:", result["risk_analysis"]["risk_level"], result["risk_analysis"]["risk_score"])
    print("Affected trains:")
    for t in sim["affected_trains"]:
        print(f"  {t['train_number']} {t['train_name']} delay={t['delay_minutes']}min")
    print("Candidates:", [(c["start_time"], c["end_time"], c["score"]) for c in result.get("candidate_windows", {}).get("candidates", [])])

    print()
    print("=== VERSION 2 (with officer feedback) ===")
    feedback = {
        "rejection_reason": "Important passenger train affected. Avoid 10:00-13:00",
        "avoid_time": "10:00-13:00",
    }
    result2 = run_workflow(req, train_data, 2, feedback)
    print("Status:", result2.get("status"))
    if result2.get("status") == "REPORT_READY":
        print("Window:", result2["selected_window"])
        sim2 = result2["simulation_result"]
        print("Affected:", sim2["total_trains_affected"])
        print("Delay:", sim2["total_delay_minutes"])
        print("Risk:", result2["risk_analysis"]["risk_level"], result2["risk_analysis"]["risk_score"])
        print("Affected trains:")
        for t in sim2["affected_trains"]:
            print(f"  {t['train_number']} {t['train_name']} delay={t['delay_minutes']}min")
        print("Candidates:", [(c["start_time"], c["end_time"], c["score"]) for c in result2.get("candidate_windows", {}).get("candidates", [])])
