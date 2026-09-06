from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database.connection import get_db
from app.models.models import MaintenanceRequest, BlockPlan, OfficerDecision, AuditLog, User, Train
from app.schemas.schemas import RejectRequest
from app.websocket.handler import manager
from app.auth.dependencies import require_officer

router = APIRouter(prefix="/api", tags=["officer"])


def _launch_replan(db: Session, plan: BlockPlan, request_obj: MaintenanceRequest) -> int:
    """Start the agentic workflow for the next plan version in a background
    thread, streaming live progress. Returns the new plan version."""
    new_version = plan.version + 1

    decision = db.query(OfficerDecision).filter(
        OfficerDecision.request_id == plan.request_id,
        OfficerDecision.plan_version == plan.version,
        OfficerDecision.decision == "REJECTED",
    ).order_by(OfficerDecision.id.desc()).first()

    officer_feedback = None
    if decision and decision.rejection_reason:
        officer_feedback = {
            "rejection_reason": decision.rejection_reason,
            "preferred_time": decision.suggested_change,
            "avoid_time": decision.avoid_time,
            "additional_constraint": decision.additional_constraint,
        }

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

    request_data = {
        "id": request_obj.id,
        "department": request_obj.department,
        "maintenance_type": request_obj.maintenance_type,
        "location": request_obj.location,
        "section": request_obj.section,
        "requested_date": request_obj.requested_date,
        "preferred_start": request_obj.preferred_start,
        "preferred_end": request_obj.preferred_end,
        "duration_minutes": request_obj.duration_minutes,
        "priority": request_obj.priority,
        "description": request_obj.description,
        "work_type": request_obj.work_type,
        "track_no": request_obj.track_no,
        "equipment": request_obj.equipment,
        "crew_size": request_obj.crew_size,
        "est_material_cost": request_obj.est_material_cost,
        "weather_sensitive": request_obj.weather_sensitive,
        "special_instructions": request_obj.special_instructions,
    }

    request_id = plan.request_id
    rejected_version = plan.version

    def do_replan():
        from app.database.connection import SessionLocal
        from app.graph.workflow import run_workflow
        from app.models.models import AgentResult
        import asyncio

        bg_db = SessionLocal()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def emit_step(name, data):
            try:
                loop.run_until_complete(manager.send_to_request(request_id, name, data))
            except Exception:
                pass

        try:
            result = run_workflow(request_data, train_data, new_version, officer_feedback, emit_event=emit_step)

            for step in result.get("agent_results", []):
                bg_db.add(AgentResult(
                    request_id=request_id,
                    plan_version=new_version,
                    agent_name=step.get("agent", "unknown"),
                    output_data=step.get("data", {}),
                    reasoning_summary=f"Replan step: {step.get('status', 'unknown')}",
                    status=step.get("status", "completed"),
                    start_time=datetime.utcnow(),
                    end_time=datetime.utcnow(),
                ))

            if result.get("status") == "REPORT_READY":
                selected = result.get("selected_window", {})
                opt = result.get("optimization_result", {})
                risk = result.get("risk_analysis", {})
                sim = result.get("simulation_result", {})

                bg_db.add(BlockPlan(
                    request_id=request_id,
                    version=new_version,
                    proposed_date=request_data.get("requested_date", ""),
                    start_time=selected.get("start_time", "10:00"),
                    end_time=selected.get("end_time", "12:00"),
                    duration_minutes=selected.get("duration_minutes", request_data.get("duration_minutes", 120)),
                    score=opt.get("objective_score", 0),
                    risk_score=risk.get("risk_score", 0),
                    confidence=result.get("decision_fusion", {}).get("confidence", 85),
                    affected_trains=sim.get("affected_trains", []),
                    estimated_delay_minutes=sim.get("total_delay_minutes", 0),
                    status="PENDING_REVIEW",
                    report_data=result.get("report", {}),
                ))

                req_ref = bg_db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
                if req_ref:
                    req_ref.status = "REPORT_READY"
                bg_db.add(AuditLog(
                    request_id=request_id,
                    actor="AI System",
                    action="REPLAN_COMPLETE",
                    details=f"Replanning V{new_version} completed (rejected V{rejected_version})",
                ))
                completed_status = result.get("status")
            else:
                req_ref = bg_db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
                if req_ref:
                    req_ref.status = "FAILED"
                bg_db.add(AuditLog(
                    request_id=request_id,
                    actor="AI System",
                    action="REPLAN_FAILED",
                    details=f"Replanning V{new_version} could not produce a feasible plan",
                ))
                completed_status = result.get("status", "FAILED")

            bg_db.commit()
            try:
                loop.run_until_complete(manager.send_to_request(request_id, "replanning_completed", {
                    "request_id": request_id,
                    "new_version": new_version,
                    "status": completed_status,
                }))
                loop.run_until_complete(manager.send_to_request(request_id, "report_ready", {
                    "request_id": request_id,
                    "plan_version": new_version,
                    "status": completed_status,
                }))
            except Exception:
                pass
        except Exception as e:
            try:
                req_ref = bg_db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
                if req_ref:
                    req_ref.status = "FAILED"
                bg_db.add(AuditLog(
                    request_id=request_id,
                    actor="AI System",
                    action="REPLAN_ERROR",
                    details=f"V{new_version} replan error: {e}",
                ))
                bg_db.commit()
            except Exception:
                pass
        finally:
            try:
                loop.close()
            except Exception:
                pass
            bg_db.close()

    import threading
    threading.Thread(target=do_replan, daemon=True).start()
    return new_version


@router.get("/officer/pending")
def get_pending(
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
):
    requests = db.query(MaintenanceRequest).filter(
        MaintenanceRequest.status.in_(["REPORT_READY", "AWAITING_OFFICER", "REPLANNING"])
    ).order_by(MaintenanceRequest.updated_at.desc()).all()

    result = []
    for r in requests:
        engineer = db.query(User).filter(User.id == r.engineer_id).first()
        latest_plan = db.query(BlockPlan).filter(BlockPlan.request_id == r.id).order_by(BlockPlan.version.desc()).first()
        result.append({
            "id": r.id,
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
            "latest_plan": {
                "id": latest_plan.id,
                "version": latest_plan.version,
                "start_time": latest_plan.start_time,
                "end_time": latest_plan.end_time,
                "risk_score": latest_plan.risk_score,
                "confidence": latest_plan.confidence,
                "affected_trains": latest_plan.affected_trains,
                "estimated_delay_minutes": latest_plan.estimated_delay_minutes,
            } if latest_plan else None,
        })

    all_requests = db.query(MaintenanceRequest).all()
    return {
        "pending": result,
        "stats": {
            "pending_approvals": len([r for r in all_requests if r.status in ("REPORT_READY", "AWAITING_OFFICER")]),
            "high_risk": len([r for r in all_requests if r.status == "AWAITING_OFFICER"]),
            "replanning": len([r for r in all_requests if r.status == "REPLANNING"]),
            "approved_today": len([r for r in all_requests if r.status == "APPROVED"]),
            "published": len([r for r in all_requests if r.status == "PUBLISHED"]),
        },
    }


@router.post("/plans/{plan_id}/approve")
async def approve_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
):
    plan = db.query(BlockPlan).filter(BlockPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan.status = "APPROVED"
    block_count = db.query(BlockPlan).filter(BlockPlan.status == "APPROVED").count() + 1
    plan.block_id = f"RS-BLK-2026-{block_count:05d}"

    request_obj = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == plan.request_id).first()
    if request_obj:
        request_obj.status = "APPROVED"

    decision = OfficerDecision(
        request_id=plan.request_id,
        plan_version=plan.version,
        officer_id=officer.id,
        decision="APPROVED",
        created_at=datetime.utcnow(),
    )
    db.add(decision)

    audit = AuditLog(
        request_id=plan.request_id,
        actor=officer.name,
        action="PLAN_APPROVED",
        details=f"Plan V{plan.version} approved by {officer.name}. Block ID: {plan.block_id}",
    )
    db.add(audit)

    db.commit()

    try:
        await manager.send_to_request(plan.request_id, "plan_approved", {
            "plan_id": plan.id,
            "version": plan.version,
            "block_id": plan.block_id,
        })
    except Exception:
        pass

    return {
        "message": "Plan approved and published",
        "plan_id": plan.id,
        "block_id": plan.block_id,
        "version": plan.version,
    }


@router.post("/plans/{plan_id}/reject")
async def reject_plan(
    plan_id: int,
    req: RejectRequest,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
):
    if not req.rejection_reason or not req.rejection_reason.strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    plan = db.query(BlockPlan).filter(BlockPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan.status = "REJECTED"

    request_obj = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == plan.request_id).first()
    if request_obj:
        request_obj.status = "REPLANNING"

    decision = OfficerDecision(
        request_id=plan.request_id,
        plan_version=plan.version,
        officer_id=officer.id,
        decision="REJECTED",
        rejection_reason=req.rejection_reason,
        suggested_change=req.preferred_time,
        avoid_time=req.avoid_time,
        additional_constraint=req.additional_constraint,
        created_at=datetime.utcnow(),
    )
    db.add(decision)

    audit = AuditLog(
        request_id=plan.request_id,
        actor=officer.name,
        action="PLAN_REJECTED",
        details=f"Plan V{plan.version} rejected by {officer.name}. Reason: {req.rejection_reason}",
    )
    db.add(audit)

    db.commit()

    try:
        await manager.send_to_request(plan.request_id, "plan_rejected", {
            "plan_id": plan.id,
            "version": plan.version,
            "reason": req.rejection_reason,
        })
    except Exception:
        pass

    new_version = _launch_replan(db, plan, request_obj)

    return {
        "message": "Plan rejected. AI replanning initiated.",
        "plan_id": plan.id,
        "version": plan.version,
        "new_version": new_version,
    }


@router.post("/plans/{plan_id}/replan")
async def replan(
    plan_id: int,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
):
    plan = db.query(BlockPlan).filter(BlockPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    request_obj = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == plan.request_id).first()
    if not request_obj:
        raise HTTPException(status_code=404, detail="Request not found")

    request_obj.status = "REPLANNING"
    db.commit()

    new_version = _launch_replan(db, plan, request_obj)

    return {"message": "Replanning initiated", "new_version": new_version}
