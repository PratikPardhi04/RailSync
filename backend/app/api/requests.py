from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import asyncio
import threading

from app.database.connection import get_db
from app.models.models import MaintenanceRequest, BlockPlan, AgentResult, AuditLog, Train, User
from app.schemas.schemas import MaintenanceRequestCreate, MaintenanceRequestResponse, BlockPlanResponse, AgentResultResponse
from app.graph.workflow import run_workflow
from app.websocket.handler import manager
from app.auth.dependencies import require_engineer

router = APIRouter(prefix="/api", tags=["requests"])


def _get_current_user(request_obj, db):
    engineer = db.query(User).filter(User.id == request_obj.engineer_id).first()
    return engineer.name if engineer else "Unknown"


@router.post("/requests")
def create_request(
    req: MaintenanceRequestCreate,
    db: Session = Depends(get_db),
    engineer: User = Depends(require_engineer),
):
    mr = MaintenanceRequest(
        engineer_id=engineer.id,
        department=req.department,
        maintenance_type=req.maintenance_type,
        location=req.location,
        section=req.section,
        requested_date=req.requested_date,
        preferred_start=req.preferred_start,
        preferred_end=req.preferred_end,
        duration_minutes=req.duration_minutes,
        priority=req.priority,
        description=req.description,
        work_type=req.work_type,
        track_no=req.track_no,
        equipment=req.equipment,
        crew_size=req.crew_size,
        est_material_cost=req.est_material_cost,
        weather_sensitive=req.weather_sensitive,
        special_instructions=req.special_instructions,
        request_metadata=req.request_metadata or {},
        status="PENDING",
    )
    db.add(mr)
    db.commit()
    db.refresh(mr)

    audit = AuditLog(request_id=mr.id, actor=engineer.name, action="REQUEST_SUBMITTED", details=f"Maintenance request submitted by {engineer.name} for {req.section}")
    db.add(audit)
    db.commit()

    return {"id": mr.id, "request_id": mr.id, "status": mr.status, "message": "Request submitted successfully"}


@router.get("/requests")
def list_requests(db: Session = Depends(get_db)):
    requests = db.query(MaintenanceRequest).order_by(MaintenanceRequest.created_at.desc()).all()
    result = []
    for r in requests:
        engineer = db.query(User).filter(User.id == r.engineer_id).first()
        latest_plan = db.query(BlockPlan).filter(BlockPlan.request_id == r.id).order_by(BlockPlan.version.desc()).first()
        result.append({
            "id": r.id,
            "engineer_id": r.engineer_id,
            "engineer_name": engineer.name if engineer else "Unknown",
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
            "status": r.status,
            "current_version": latest_plan.version if latest_plan else 0,
            "request_metadata": r.request_metadata or {},
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        })
    return result


@router.get("/requests/{request_id}")
def get_request(request_id: int, db: Session = Depends(get_db)):
    r = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found")
    engineer = db.query(User).filter(User.id == r.engineer_id).first()
    plans = db.query(BlockPlan).filter(BlockPlan.request_id == r.id).order_by(BlockPlan.version.desc()).all()
    return {
        "id": r.id,
        "engineer_id": r.engineer_id,
        "engineer_name": engineer.name if engineer else "Unknown",
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
        "status": r.status,
        "request_metadata": r.request_metadata or {},
        "plans": [
            {
                "id": p.id,
                "version": p.version,
                "proposed_date": p.proposed_date,
                "start_time": p.start_time,
                "end_time": p.end_time,
                "duration_minutes": p.duration_minutes,
                "score": p.score,
                "risk_score": p.risk_score,
                "confidence": p.confidence,
                "affected_trains": p.affected_trains,
                "estimated_delay_minutes": p.estimated_delay_minutes,
                "status": p.status,
                "block_id": p.block_id,
                "created_at": p.created_at.isoformat() if p.created_at else "",
            }
            for p in plans
        ],
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "updated_at": r.updated_at.isoformat() if r.updated_at else "",
    }


@router.get("/requests/{request_id}/plans")
def get_plans(request_id: int, db: Session = Depends(get_db)):
    plans = db.query(BlockPlan).filter(BlockPlan.request_id == request_id).order_by(BlockPlan.version.desc()).all()
    return [
        {
            "id": p.id,
            "version": p.version,
            "proposed_date": p.proposed_date,
            "start_time": p.start_time,
            "end_time": p.end_time,
            "duration_minutes": p.duration_minutes,
            "score": p.score,
            "risk_score": p.risk_score,
            "confidence": p.confidence,
            "affected_trains": p.affected_trains,
            "estimated_delay_minutes": p.estimated_delay_minutes,
            "status": p.status,
            "block_id": p.block_id,
            "created_at": p.created_at.isoformat() if p.created_at else "",
        }
        for p in plans
    ]


@router.post("/requests/{request_id}/analyze")
async def analyze_request(
    request_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    engineer: User = Depends(require_engineer),
):
    r = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found")

    r.status = "AI_ANALYSIS"
    db.commit()

    existing_plans = db.query(BlockPlan).filter(BlockPlan.request_id == request_id).all()
    plan_version = max([p.version for p in existing_plans], default=0) + 1

    trains = db.query(Train).all()
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

    officer_feedback = None
    if plan_version > 1:
        from app.models.models import OfficerDecision
        prev_decision = db.query(OfficerDecision).filter(
            OfficerDecision.request_id == request_id,
            OfficerDecision.plan_version == plan_version - 1,
            OfficerDecision.decision == "REJECTED",
        ).first()
        if prev_decision:
            officer_feedback = {
                "rejection_reason": prev_decision.rejection_reason,
                "preferred_time": prev_decision.suggested_change,
                "avoid_time": prev_decision.avoid_time,
                "additional_constraint": prev_decision.additional_constraint,
            }

    request_data = {
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

    def run_in_background():
        from app.database.connection import SessionLocal
        bg_db = SessionLocal()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def emit_step(name, data):
            try:
                loop.run_until_complete(manager.send_to_request(request_id, name, data))
            except Exception:
                pass

        try:
            result = run_workflow(request_data, train_data, plan_version, officer_feedback, emit_event=emit_step)

            for step in result.get("agent_results", []):
                ar = AgentResult(
                    request_id=request_id,
                    plan_version=plan_version,
                    agent_name=step.get("agent", "unknown"),
                    output_data=step.get("data", {}),
                    reasoning_summary=f"Step completed: {step.get('status', 'unknown')}",
                    status=step.get("status", "completed"),
                    start_time=datetime.utcnow(),
                    end_time=datetime.utcnow(),
                )
                bg_db.add(ar)

            if result.get("status") == "REPORT_READY":
                selected = result.get("selected_window", {})
                opt = result.get("optimization_result", {})
                risk = result.get("risk_analysis", {})
                sim = result.get("simulation_result", {})

                bp = BlockPlan(
                    request_id=request_id,
                    version=plan_version,
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
                )
                bg_db.add(bp)

                req_ref = bg_db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
                if req_ref:
                    req_ref.status = "REPORT_READY"
                audit = AuditLog(request_id=request_id, actor="AI System", action="ANALYSIS_COMPLETE", details=f"Plan V{plan_version} generated. Window: {selected.get('start_time', 'N/A')}-{selected.get('end_time', 'N/A')}")
                bg_db.add(audit)
            else:
                req_ref = bg_db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
                if req_ref:
                    req_ref.status = "FAILED"
                audit = AuditLog(request_id=request_id, actor="AI System", action="ANALYSIS_FAILED", details=str(result.get("error", "Unknown error")))
                bg_db.add(audit)

            bg_db.commit()
            try:
                loop.run_until_complete(manager.send_to_request(request_id, "report_ready", {
                    "request_id": request_id,
                    "plan_version": plan_version,
                    "status": result.get("status"),
                }))
            except Exception:
                pass
        except Exception as e:
            try:
                req_ref = bg_db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
                if req_ref:
                    req_ref.status = "FAILED"
                audit = AuditLog(request_id=request_id, actor="AI System", action="ANALYSIS_ERROR", details=str(e))
                bg_db.add(audit)
                bg_db.commit()
            except Exception:
                pass
        finally:
            try:
                loop.close()
            except Exception:
                pass
            bg_db.close()

    def start_bg():
        try:
            run_in_background()
        except Exception:
            pass

    t = threading.Thread(target=start_bg, daemon=True)
    t.start()

    return {"message": "Analysis started", "request_id": request_id, "plan_version": plan_version}


@router.get("/requests/{request_id}/agents")
def get_agent_results(request_id: int, plan_version: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(AgentResult).filter(AgentResult.request_id == request_id)
    if plan_version:
        query = query.filter(AgentResult.plan_version == plan_version)
    results = query.order_by(AgentResult.created_at.asc()).all()
    return [
        {
            "id": r.id,
            "agent_name": r.agent_name,
            "output_data": r.output_data,
            "reasoning_summary": r.reasoning_summary,
            "status": r.status,
            "plan_version": r.plan_version,
            "start_time": r.start_time.isoformat() if r.start_time else None,
            "end_time": r.end_time.isoformat() if r.end_time else None,
        }
        for r in results
    ]


@router.get("/requests/{request_id}/report")
def get_report(request_id: int, plan_version: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(BlockPlan).filter(BlockPlan.request_id == request_id)
    if plan_version:
        query = query.filter(BlockPlan.version == plan_version)
    plan = query.order_by(BlockPlan.version.desc()).first()
    if not plan:
        raise HTTPException(status_code=404, detail="No plan found")

    agent_results = db.query(AgentResult).filter(
        AgentResult.request_id == request_id,
        AgentResult.plan_version == plan.version,
    ).all()

    request_obj = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()

    return {
        "plan": {
            "id": plan.id,
            "version": plan.version,
            "proposed_date": plan.proposed_date,
            "start_time": plan.start_time,
            "end_time": plan.end_time,
            "duration_minutes": plan.duration_minutes,
            "score": plan.score,
            "risk_score": plan.risk_score,
            "confidence": plan.confidence,
            "affected_trains": plan.affected_trains,
            "estimated_delay_minutes": plan.estimated_delay_minutes,
            "status": plan.status,
            "block_id": plan.block_id,
            "report_data": plan.report_data or {},
        },
        "request": {
            "id": request_obj.id if request_obj else request_id,
            "department": request_obj.department if request_obj else "",
            "maintenance_type": request_obj.maintenance_type if request_obj else "",
            "location": request_obj.location if request_obj else "",
            "section": request_obj.section if request_obj else "",
            "requested_date": request_obj.requested_date if request_obj else "",
            "preferred_start": request_obj.preferred_start if request_obj else "",
            "preferred_end": request_obj.preferred_end if request_obj else "",
            "duration_minutes": request_obj.duration_minutes if request_obj else 0,
            "priority": request_obj.priority if request_obj else "",
            "description": request_obj.description if request_obj else "",
            "work_type": request_obj.work_type if request_obj else None,
            "track_no": request_obj.track_no if request_obj else None,
            "equipment": request_obj.equipment if request_obj else None,
            "crew_size": request_obj.crew_size if request_obj else None,
            "est_material_cost": request_obj.est_material_cost if request_obj else None,
            "weather_sensitive": request_obj.weather_sensitive if request_obj else None,
            "special_instructions": request_obj.special_instructions if request_obj else None,
        },
        "agent_results": [
            {
                "agent_name": a.agent_name,
                "output_data": a.output_data,
                "reasoning_summary": a.reasoning_summary,
                "status": a.status,
            }
            for a in agent_results
        ],
    }


@router.get("/requests/{request_id}/history")
def get_history(request_id: int, db: Session = Depends(get_db)):
    plans = db.query(BlockPlan).filter(BlockPlan.request_id == request_id).order_by(BlockPlan.version.asc()).all()
    decisions = db.query(AuditLog).filter(AuditLog.request_id == request_id).order_by(AuditLog.timestamp.asc()).all()
    return {
        "plans": [
            {
                "version": p.version,
                "start_time": p.start_time,
                "end_time": p.end_time,
                "status": p.status,
                "risk_score": p.risk_score,
                "block_id": p.block_id,
                "created_at": p.created_at.isoformat() if p.created_at else "",
            }
            for p in plans
        ],
        "audit_trail": [
            {
                "actor": a.actor,
                "action": a.action,
                "details": a.details,
                "timestamp": a.timestamp.isoformat() if a.timestamp else "",
            }
            for a in decisions
        ],
    }
