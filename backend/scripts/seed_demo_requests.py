"""Seed demo pre-requests and run the real deterministic workflow for each.

Each request is persisted like the `/analyze` endpoint does, so the engineer
dashboard shows authentic BlockPlans + AgentResults + officer reports with no
hand-authored numbers. The scenarios are chosen so their outputs demonstrate
distinct operational outcomes:

  1. Standard busy corridor (whole pipeline incl. auto-replan / diversions).
  2. No train affected (quiet section, zero impact).
  3. Few trains affected but NOT diverted (passengers held, no reroute).
  4. Train allowed to pass in between the block with minor regulation (DELAY).

Run from backend/:  python scripts/seed_demo_requests.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from dotenv import load_dotenv

    _here = os.path.dirname(os.path.abspath(__file__))
    for _candidate in (os.path.join(_here, "..", ".env"), os.path.join(_here, "..", "..", ".env")):
        if os.path.exists(_candidate):
            load_dotenv(_candidate)
            break
except Exception:
    pass

from datetime import date, timedelta

from app.database.connection import SessionLocal, init_db
from app.models.models import (
    AgentResult, AuditLog, BlockExecution, BlockPlan, MaintenanceRequest,
    OfficerDecision, Train, User,
)
from app.graph.workflow import run_workflow


def tomorrow(days: int = 1) -> str:
    return (date.today() + timedelta(days=days)).strftime("%Y-%m-%d")


def build_request_data(r: MaintenanceRequest) -> dict:
    return {
        "id": r.id,
        "department": r.department,
        "maintenance_type": r.maintenance_type,
        "location": r.location,
        "section": r.section,
        "requested_date": r.requested_date,
        "preferred_start": r.preferred_start,
        "preferred_end": r.preferred_end,
        "duration_minutes": r.duration_minutes,
        "priority": r.priority,
        "description": r.description,
        "work_type": r.work_type,
        "track_no": r.track_no,
        "equipment": r.equipment,
        "crew_size": r.crew_size,
        "est_material_cost": r.est_material_cost,
        "weather_sensitive": r.weather_sensitive,
        "special_instructions": r.special_instructions,
        "request_metadata": r.request_metadata or {},
    }


# ---------------------------------------------------------------------------
# Demo scenario definitions (outcome-typed pre-requests).
# ---------------------------------------------------------------------------
def scenarios(engineer_id: int) -> list:
    return [
        # 1. Standard busy corridor - exercises the full pipeline incl. gate
        #    replan (Vande Bharat protection) and Yerwada diversion proposals.
        dict(
            engineer_id=engineer_id,
            department="Engineering",
            maintenance_type="Track Maintenance",
            location="Pune Division",
            section="Shivajinagar - Khadki",
            requested_date=tomorrow(1),
            preferred_start="10:00",
            preferred_end="12:00",
            duration_minutes=120,
            priority="HIGH",
            description=(
                "Deep ballast renewal and rail-pad replacement on the busy Down Main between "
                "Shivajinagar and Khadki. High axle-load corridor traffic has accelerated wear "
                "on turnout 42 approach; renewal is required before the monsoon."
            ),
            work_type="Track Maintenance",
            track_no="Down Main Line",
            equipment="Tamping machine, ballast regulator, tower wagon, rail pads",
            crew_size=12,
            est_material_cost=475000,
            weather_sensitive="NO",
            special_instructions=(
                "Block: MAINTENANCE BLOCK, Track Down Main Line. Direction: UP. "
                "Isolation required: NO. Expected operational impact: multiple express and "
                "passenger trains; AI should select least-impact window and propose rerouting "
                "via the Yerwada diversion where feasible. Priority train restrictions: Do not "
                "delay Mumbai Rajdhani, Shatabdi or Vande Bharat beyond 10 min."
            ),
            request_metadata={
                "division": "Pune Division",
                "location_km": "KM 128/600 - 129/200 (Down Main, turnout 42 approach)",
                "asset_id": "BFT-1285-OW",
                "reason": "Track geometry measurements exceeded maintenance limits (alignment +7 mm).",
                "machines": "Tamping machine + ballast regulator",
                "estimated_workforce": 12,
                "track_line": "Down Main Line",
                "block_type": "MAINTENANCE BLOCK",
                "direction": "UP",
                "isolation_required": "NO",
                "expected_operational_impact": "Likely to affect multiple express and passenger trains.",
                "priority_train_restrictions": "Do not delay Mumbai Rajdhani, Shatabdi or Vande Bharat beyond 10 min.",
                "attachments": [],
            },
        ),
        # 2. No train affected - sparse section, daytime quiet window.
        dict(
            engineer_id=engineer_id,
            department="Engineering",
            maintenance_type="Track Reconditioning",
            location="Pune Division",
            section="Pune - Lonavala",
            requested_date=tomorrow(2),
            preferred_start="10:00",
            preferred_end="11:30",
            duration_minutes=90,
            priority="MEDIUM",
            description=(
                "Reconditioning of track geometry and sleeper realignment on the Pune - Lonavala "
                "section. Ghat section wear repair."
            ),
            work_type="Track Reconditioning",
            track_no="Down Main Line",
            equipment="Track tamping machine, geometry trolley",
            crew_size=8,
            est_material_cost=180000,
            weather_sensitive="NO",
            special_instructions=(
                "Block: MAINTENANCE BLOCK, Track Down Main Line. Direction: UP. "
                "Isolation required: NO. Expected operational impact: quiet daytime window; "
                "no scheduled trains expected within the proposed window."
            ),
            request_metadata={
                "division": "Pune Division",
                "location_km": "KM 94/400 - 95/020",
                "asset_id": "TRK-PULV-094",
                "reason": "Ghat-section geometry drift observed during track recording run.",
                "machines": "Track tamping machine",
                "estimated_workforce": 8,
                "track_line": "Down Main Line",
                "block_type": "MAINTENANCE BLOCK",
                "direction": "UP",
                "isolation_required": "NO",
                "expected_operational_impact": "Low - sparse section, no trains in window.",
                "priority_train_restrictions": "",
                "attachments": [],
            },
        ),
        # 3. Few trains affected but NOT diverted - passengers held, no reroute.
        dict(
            engineer_id=engineer_id,
            department="S&T",
            maintenance_type="Signal Maintenance",
            location="Pune Division",
            section="Shivajinagar - Hadapsar",
            requested_date=tomorrow(3),
            preferred_start="18:05",
            preferred_end="19:05",
            duration_minutes=60,
            priority="MEDIUM",
            description=(
                "Signal relay and interlocking health checks on the broad-gauge branch towards "
                "Hadapsar goods yard, including replacement of a defective point machine."
            ),
            work_type="Signal Maintenance",
            track_no="Branch Line",
            equipment="Signal test kit, point machine spares",
            crew_size=6,
            est_material_cost=95000,
            weather_sensitive="NO",
            special_instructions=(
                "Block: SIGNAL WORKS, Track Branch Line. Direction: BOTH. "
                "Isolation required: NO. Expected operational impact: 1-2 passenger trains may "
                "be regulated; no premium services on this branch, no diversion expected."
            ),
            request_metadata={
                "division": "Pune Division",
                "location_km": "Station area - Shivajinagar end",
                "asset_id": "SIG-SY-07",
                "reason": "Point machine P7 showing slow throw during pre-monsoon inspection.",
                "machines": "Signal test kit",
                "estimated_workforce": 6,
                "track_line": "Branch Line",
                "block_type": "SIGNAL WORKS",
                "direction": "BOTH",
                "isolation_required": "NO",
                "expected_operational_impact": "1-2 passenger trains regulated, no diversion.",
                "priority_train_restrictions": "",
                "attachments": [],
            },
        ),
        # 4. Train allowed to pass in between the block - minor DELAY only.
        dict(
            engineer_id=engineer_id,
            department="Engineering",
            maintenance_type="Bridge Inspection",
            location="Pune Division",
            section="Khadki - Dapodi",
            requested_date=tomorrow(4),
            preferred_start="08:00",
            preferred_end="08:45",
            duration_minutes=45,
            priority="LOW",
            description=(
                "Under-slung inspection of bridge 42 span over the Mula river approach, "
                "including soffit check for cracking and pier scour assessment."
            ),
            work_type="Bridge Inspection",
            track_no="Up/Down Main Line",
            equipment="Under-slung inspection trolley, endoscope, scour probe",
            crew_size=5,
            est_material_cost=60000,
            weather_sensitive="YES",
            special_instructions=(
                "Block: NORMAL SPEED RESTRICTION, Track Up/Down Main Line. Direction: BOTH. "
                "Isolation required: NO. Expected operational impact: one local passenger may "
                "pass through the break with a short regulation - train should be allowed to "
                "pass in between the inspection window wherever possible."
            ),
            request_metadata={
                "division": "Pune Division",
                "location_km": "Bridge 42, Khadki - Dapodi",
                "asset_id": "BR-42-MULA",
                "reason": "Soffit cracking observed near pier 3; needs visual + endoscopic check.",
                "machines": "Inspection trolley",
                "estimated_workforce": 5,
                "track_line": "Up/Down Main Line",
                "block_type": "NORMAL SPEED RESTRICTION",
                "direction": "BOTH",
                "isolation_required": "NO",
                "expected_operational_impact": "Minor - local passenger allowed past with short hold.",
                "priority_train_restrictions": "",
                "attachments": [],
            },
        ),
    ]


def clear_requests(db):
    db.query(BlockExecution).delete()
    db.query(OfficerDecision).delete()
    db.query(AgentResult).delete()
    db.query(BlockPlan).delete()
    db.query(AuditLog).delete()
    db.query(MaintenanceRequest).delete()
    db.commit()


def seed_demo_requests(db=None, force: bool = False) -> int:
    """Idempotently seed the demo request corpus through the real workflow.

    Only runs when there are no existing MaintenanceRequest rows (or when
    ``force=True``), so it is safe to call from server startup on a fresh DB.
    Returns the number of requests created.
    """
    own_db = db is None
    if own_db:
        init_db()
        db = SessionLocal()
    try:
        if force:
            # A force reseed is a full regenerate of the demo corpus: clear any
            # existing requests first so we never duplicate MR-1..MR-4.
            clear_requests(db)
        else:
            existing = db.query(MaintenanceRequest).count()
            if existing > 0:
                return 0

        engineer = db.query(User).filter(User.role == "engineer").order_by(User.id).first()
        if not engineer:
            print("No engineer user found - run seed_database.py first.")
            return 0
        engineer_id = engineer.id

        trains = db.query(Train).order_by(Train.arrival_time).all()
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
            for t in trains
        ]

        created = 0
        for spec in scenarios(engineer_id):
            r = MaintenanceRequest(status="PENDING", **spec)
            db.add(r)
            db.commit()
            db.refresh(r)

            req_data = build_request_data(r)
            result = run_workflow(req_data, train_data, plan_version=1, officer_feedback=None)

            if result.get("status") == "REPORT_READY":
                for step in result.get("agent_results", []):
                    db.add(AgentResult(
                        request_id=r.id,
                        plan_version=1,
                        agent_name=step.get("agent", "unknown"),
                        output_data=step.get("data", {}),
                        reasoning_summary=f"Step completed: {step.get('status', 'unknown')}",
                        status=step.get("status", "completed"),
                    ))

                selected = result.get("selected_window", {})
                opt = result.get("optimization_result", {})
                risk = result.get("risk_analysis", {})
                sim = result.get("simulation_result", {})
                db.add(BlockPlan(
                    request_id=r.id,
                    version=1,
                    proposed_date=r.requested_date,
                    start_time=selected.get("start_time", "10:00"),
                    end_time=selected.get("end_time", "12:00"),
                    duration_minutes=selected.get("duration_minutes", r.duration_minutes),
                    score=opt.get("objective_score", 0),
                    risk_score=risk.get("risk_score", 0),
                    confidence=result.get("decision_fusion", {}).get("confidence", 85),
                    affected_trains=sim.get("affected_trains", []),
                    estimated_delay_minutes=sim.get("total_delay_minutes", 0),
                    status="PENDING_REVIEW",
                    report_data=result.get("report", {}),
                ))
                r.status = "REPORT_READY"
                created += 1
            else:
                r.status = "FAILED"
                db.rollback()
                print(f"  [FAILED] request {r.section}: {result.get('error', 'unknown')}")

            db.add(AuditLog(
                request_id=r.id,
                actor="AI System",
                action="ANALYSIS_COMPLETE" if r.status == "REPORT_READY" else "ANALYSIS_FAILED",
                details="Plan V1 generated." if r.status == "REPORT_READY" else "",
            ))
            db.commit()

        print(f"[seed_demo_requests] created {created} demo request(s) with real workflow reports.")
        return created
    finally:
        if own_db:
            db.close()


def main():
    init_db()
    db = SessionLocal()
    try:
        clear_requests(db)
        created = seed_demo_requests(db=db, force=True)
        print(f"Seeded {created} demo pre-requests (all reports from real deterministic workflow).")
    finally:
        db.close()


if __name__ == "__main__":
    main()