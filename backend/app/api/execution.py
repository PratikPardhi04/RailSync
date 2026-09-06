from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database.connection import get_db
from app.models.models import BlockPlan, BlockExecution, MaintenanceRequest, AuditLog, User
from app.auth.dependencies import require_officer, require_engineer
from app.services.block_notice import generate_artifacts
from app.websocket.handler import manager

router = APIRouter(prefix="/api/execution", tags=["execution"])

FLOW = ["SANCTIONED", "IN_POSITION", "BLOCK_ACTIVE", "RELEASED", "COMPLETED"]


def _get_plan(db: Session, plan_id: int) -> BlockPlan:
    plan = db.query(BlockPlan).filter(BlockPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status not in ("APPROVED", "PUBLISHED"):
        raise HTTPException(status_code=400, detail="Plan must be approved before execution")
    if not plan.block_id:
        raise HTTPException(status_code=400, detail="Plan has no assigned block id")
    return plan


def _get_exec(db: Session, plan_id: int) -> BlockExecution:
    ex = db.query(BlockExecution).filter(BlockExecution.plan_id == plan_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="No execution started for this block")
    return ex


def _audit(db: Session, request_id: int, actor: str, action: str, details: str):
    db.add(AuditLog(request_id=request_id, actor=actor, action=action, details=details))


@router.get("/plans/{plan_id}")
def get_execution(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(BlockPlan).filter(BlockPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    ex = db.query(BlockExecution).filter(BlockExecution.plan_id == plan_id).first()
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == plan.request_id).first()
    return {
        "plan_id": plan.id,
        "version": plan.version,
        "block_id": ex.block_id if ex else plan.block_id,
        "request_id": plan.request_id,
        "section": req.section if req else "",
        "maintenance_type": req.maintenance_type if req else "",
        "window": f"{plan.start_time}-{plan.end_time}",
        "proposed_date": plan.proposed_date,
        "status": ex.status if ex else "NOT_STARTED",
        "sanctioned_by": ex.sanctioned_by if ex else None,
        "engineer_name": None,
        "sanctioned_at": ex.sanctioned_at.isoformat() if ex and ex.sanctioned_at else None,
        "checkin_at": ex.checkin_at.isoformat() if ex and ex.checkin_at else None,
        "block_active_at": ex.block_active_at.isoformat() if ex and ex.block_active_at else None,
        "released_at": ex.released_at.isoformat() if ex and ex.released_at else None,
        "completed_at": ex.completed_at.isoformat() if ex and ex.completed_at else None,
        "block_notice": ex.block_notice if ex else None,
        "caution_order": ex.caution_order if ex else None,
        "notes": ex.notes if ex else None,
        "plan_status": plan.status,
    }


@router.post("/plans/{plan_id}/sanction")
async def sanction_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
):
    plan = _get_plan(db, plan_id)
    existing = db.query(BlockExecution).filter(BlockExecution.plan_id == plan_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Block already has an execution session")

    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == plan.request_id).first()
    artifacts = generate_artifacts(plan, req, officer.name)

    ex = BlockExecution(
        plan_id=plan.id,
        request_id=plan.request_id,
        block_id=plan.block_id,
        status="SANCTIONED",
        sanctioned_by=officer.name,
        sanctioned_at=datetime.utcnow(),
        block_notice=artifacts["block_notice"],
        caution_order=artifacts["caution_order"],
    )
    db.add(ex)
    req.status = "SANCTIONED"
    _audit(db, plan.request_id, officer.name, "BLOCK_SANCTIONED",
           f"Block {plan.block_id} sanctioned by {officer.name}. Notice + caution order issued.")
    db.commit()
    db.refresh(ex)

    await manager.send_to_request(plan.request_id, "block_sanctioned", {
        "plan_id": plan.id, "block_id": plan.block_id, "status": ex.status,
    })
    return {
        "plan_id": plan.id,
        "block_id": plan.block_id,
        "status": ex.status,
        "block_notice": ex.block_notice,
        "caution_order": ex.caution_order,
        "message": "Block sanctioned. Notice and caution order issued.",
    }


@router.post("/plans/{plan_id}/checkin")
async def checkin_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    engineer: User = Depends(require_engineer),
):
    ex = _get_exec(db, plan_id)
    if ex.status != "SANCTIONED":
        raise HTTPException(status_code=400, detail=f"Cannot check in from status {ex.status}")
    ex.status = "IN_POSITION"
    ex.engineer_id = engineer.id
    ex.checkin_at = datetime.utcnow()
    _audit(db, ex.request_id, engineer.name, "ENGINEER_CHECKIN",
           f"Engineer {engineer.name} on site for block {ex.block_id}")
    db.commit()
    await manager.send_to_request(ex.request_id, "block_checkin", {"plan_id": plan_id, "status": ex.status})
    return {"plan_id": plan_id, "block_id": ex.block_id, "status": ex.status, "message": "Engineer on site"}


@router.post("/plans/{plan_id}/activate")
async def activate_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    engineer: User = Depends(require_engineer),
):
    ex = _get_exec(db, plan_id)
    if ex.status != "IN_POSITION":
        raise HTTPException(status_code=400, detail=f"Cannot activate from status {ex.status}")
    ex.status = "BLOCK_ACTIVE"
    ex.block_active_at = datetime.utcnow()
    _audit(db, ex.request_id, engineer.name, "BLOCK_ACTIVE",
           f"Track possession taken for block {ex.block_id} by {engineer.name}")
    db.commit()
    await manager.send_to_request(ex.request_id, "block_active", {"plan_id": plan_id, "status": ex.status})
    return {"plan_id": plan_id, "block_id": ex.block_id, "status": ex.status, "message": "Block is active"}


@router.post("/plans/{plan_id}/release")
async def release_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    engineer: User = Depends(require_engineer),
):
    ex = _get_exec(db, plan_id)
    if ex.status != "BLOCK_ACTIVE":
        raise HTTPException(status_code=400, detail=f"Cannot release from status {ex.status}")
    ex.status = "RELEASED"
    ex.released_at = datetime.utcnow()
    _audit(db, ex.request_id, engineer.name, "BLOCK_RELEASED",
           f"Track line released for block {ex.block_id} by {engineer.name}")
    db.commit()
    await manager.send_to_request(ex.request_id, "block_released", {"plan_id": plan_id, "status": ex.status})
    return {"plan_id": plan_id, "block_id": ex.block_id, "status": ex.status, "message": "Block released"}


@router.post("/plans/{plan_id}/complete")
async def complete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    engineer: User = Depends(require_engineer),
):
    ex = _get_exec(db, plan_id)
    if ex.status not in ("RELEASED", "BLOCK_ACTIVE"):
        raise HTTPException(status_code=400, detail=f"Cannot complete from status {ex.status}")
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == ex.request_id).first()
    ex.status = "COMPLETED"
    ex.completed_at = datetime.utcnow()
    if req:
        req.status = "COMPLETED"
    _audit(db, ex.request_id, engineer.name, "BLOCK_COMPLETED",
           f"Block {ex.block_id} completed and closed by {engineer.name}")
    db.commit()
    await manager.send_to_request(ex.request_id, "block_completed", {"plan_id": plan_id, "status": ex.status})
    return {"plan_id": plan_id, "block_id": ex.block_id, "status": ex.status, "message": "Block completed"}