import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.candidate_generator import run as gen_candidates
from app.database.connection import SessionLocal, init_db
from app.models.models import Train
from app.agents import traffic_agent

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

print("=== TRAFFIC ANALYSIS ===")
traffic = traffic_agent.run(req, train_data)
print("Affected trains:", traffic["total_affected"])
for t in traffic["affected_trains"]:
    print(f"  {t['train_number']} {t['train_name']} arr={t['arrival_time']} dep={t['departure_time']} delay={t['estimated_delay_minutes']}")

print()
print("=== CANDIDATE GENERATION ===")
maint = {"maintenance_duration": 120, "resource_requirements": ["crew"], "priority": "HIGH"}
hist = {"similar_cases": [], "relevant_rules": [], "recommendations": []}
result = gen_candidates(req, maint, traffic, hist, None)
print("Candidates:", result["candidates"])
print("Total evaluated:", result["total_evaluated"])
print("Constraints:", result["constraints_applied"])

print()
print("=== WITH OFFICER FEEDBACK ===")
feedback = {"rejection_reason": "Important passenger train affected. Avoid 10:00-13:00", "avoid_time": "10:00-13:00"}
result2 = gen_candidates(req, maint, traffic, hist, feedback)
print("Candidates:", result2["candidates"])
print("Total evaluated:", result2["total_evaluated"])
print("Constraints:", result2["constraints_applied"])
