import threading
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.models import BlockPlan, MaintenanceRequest, Train, AgentResult, AuditLog
from app.services import live_sim
from app.services.weather import get_weather
from app.auth.dependencies import require_officer

router = APIRouter(prefix="/api/live", tags=["live"])


class SpeedRequest(BaseModel):
    speed: int


class RunningRequest(BaseModel):
    running: bool


class JumpRequest(BaseModel):
    minutes: int


@router.get("/state")
def live_state(db: Session = Depends(get_db)):
    return live_sim.snapshot(db)


@router.post("/speed")
def set_speed(req: SpeedRequest, db: Session = Depends(get_db)):
    speed = live_sim.set_speed(db, req.speed)
    return {"speed": speed}


@router.post("/running")
def set_running(req: RunningRequest, db: Session = Depends(get_db)):
    running = live_sim.set_running(db, req.running)
    return {"running": running}


@router.post("/jump")
def jump_clock(req: JumpRequest, db: Session = Depends(get_db)):
    """Fast-forward the simulated clock by N minutes (ops drill / demo control)."""
    minutes = max(0, min(1440, int(req.minutes)))
    state = live_sim.advance(db)
    state.sim_minutes = state.sim_minutes + minutes
    state.last_tick_at = datetime.utcnow()
    db.commit()
    return {"sim_time": live_sim.fmt_minutes(state.sim_minutes), "sim_minutes": state.sim_minutes}


@router.get("/weather")
def live_weather(db: Session = Depends(get_db)):
    from app.models.models import Train
    section = "Shivajinagar - Khadki"
    t = db.query(Train).first()
    if t:
        section = t.section
    return get_weather(section)


def _background_dynamic_replan(request_id: int, plan_id: int, avoid_window: str, train_no: str):
    from app.database.connection import SessionLocal
    from app.graph.workflow import run_workflow

    bg_db = SessionLocal()
    try:
        req = bg_db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
        if not req:
            return
        existing_plans = bg_db.query(BlockPlan).filter(BlockPlan.request_id == request_id).all()
        new_version = max([p.version for p in existing_plans], default=0) + 1
        req.status = "REPLANNING"
        bg_db.commit()

        trains = bg_db.query(Train).all()
        train_data = [
            {
                "train_number": t.train_number, "train_name": t.train_name,
                "train_type": t.train_type, "priority": t.priority,
                "origin": t.origin, "destination": t.destination, "section": t.section,
                "arrival_time": t.arrival_time, "departure_time": t.departure_time,
                "average_speed": t.average_speed,
            }
            for t in trains
        ]
        request_data = {
            "id": req.id, "department": req.department, "maintenance_type": req.maintenance_type,
            "location": req.location, "section": req.section, "requested_date": req.requested_date,
            "preferred_start": req.preferred_start, "preferred_end": req.preferred_end,
            "duration_minutes": req.duration_minutes, "priority": req.priority,
            "description": req.description, "work_type": req.work_type, "track_no": req.track_no,
            "equipment": req.equipment, "crew_size": req.crew_size,
            "est_material_cost": req.est_material_cost, "weather_sensitive": req.weather_sensitive,
            "special_instructions": req.special_instructions,
        }
        officer_feedback = {
            "rejection_reason": f"Dynamic live conflict - {train_no} projected to cross the block window. Auto replanned.",
            "avoid_time": avoid_window,
            "preferred_time": None,
            "additional_constraint": None,
        }

        result = run_workflow(request_data, train_data, new_version, officer_feedback)

        for step in result.get("agent_results", []):
            bg_db.add(AgentResult(
                request_id=request_id, plan_version=new_version,
                agent_name=step.get("agent", "unknown"), output_data=step.get("data", {}),
                reasoning_summary=f"Dynamic replan step: {step.get('status', 'unknown')}",
                status=step.get("status", "completed"),
                start_time=datetime.utcnow(), end_time=datetime.utcnow(),
            ))

        if result.get("status") == "REPORT_READY":
            selected = result.get("selected_window", {})
            opt = result.get("optimization_result", {})
            risk = result.get("risk_analysis", {})
            sim = result.get("simulation_result", {})
            bg_db.add(BlockPlan(
                request_id=request_id, version=new_version,
                proposed_date=req.requested_date,
                start_time=selected.get("start_time", "10:00"),
                end_time=selected.get("end_time", "12:00"),
                duration_minutes=selected.get("duration_minutes", req.duration_minutes),
                score=opt.get("objective_score", 0),
                risk_score=risk.get("risk_score", 0),
                confidence=result.get("decision_fusion", {}).get("confidence", 85),
                affected_trains=sim.get("affected_trains", []),
                estimated_delay_minutes=sim.get("total_delay_minutes", 0),
                status="PENDING_REVIEW",
                report_data=result.get("report", {}),
            ))
            req.status = "REPORT_READY"
            bg_db.add(AuditLog(
                request_id=request_id, actor="LiveSim",
                action="DYNAMIC_REPLAN",
                details=f"Auto replan to V{new_version} due to live conflict with {train_no} at {avoid_window}",
            ))
        else:
            req.status = "FAILED"
            bg_db.add(AuditLog(
                request_id=request_id, actor="LiveSim",
                action="DYNAMIC_REPLAN_FAILED",
                details=str(result.get("error", "Unknown")),
            ))
        bg_db.commit()
    finally:
        bg_db.close()


@router.post("/dynamic-replan/{plan_id}")
def dynamic_replan(plan_id: int, db: Session = Depends(get_db), officer=Depends(require_officer)):
    plan = db.query(BlockPlan).filter(BlockPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == plan.request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    avoid_window = f"{plan.start_time}-{plan.end_time}"
    latest = db.query(BlockPlan).filter(BlockPlan.request_id == plan.request_id).order_by(BlockPlan.version.desc()).first()
    if latest and latest.id != plan.id and latest.status in ("PENDING_REVIEW", "APPROVED"):
        raise HTTPException(status_code=400, detail="A newer plan already exists for this request")

    train_no = "premium train"
    thread = threading.Thread(
        target=_background_dynamic_replan,
        args=(req.id, plan.id, avoid_window, train_no),
        daemon=True,
    )
    thread.start()

    return {"message": "Dynamic replan triggered",
            "new_version": (plan.version + 1),
            "avoid_window": avoid_window,
            "note": "AI will regenerate a compliant window and send it to the officer for approval."}