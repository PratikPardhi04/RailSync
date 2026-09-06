from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.connection import get_db
from app.models.models import MaintenanceRequest, BlockPlan, User
from app.auth.dependencies import require_engineer, require_officer

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/engineer")
def engineer_dashboard(db: Session = Depends(get_db), user: User = Depends(require_engineer)):
    all_requests = db.query(MaintenanceRequest).all()
    total = len(all_requests)
    pending = len([r for r in all_requests if r.status in ("DRAFT", "SUBMITTED", "PENDING")])
    ai_processing = len([r for r in all_requests if r.status in ("VALIDATING", "AI_ANALYSIS", "OPTIMIZING", "SIMULATING")])
    awaiting = len([r for r in all_requests if r.status in ("REPORT_READY", "AWAITING_OFFICER")])
    approved = len([r for r in all_requests if r.status == "APPROVED"])
    rejected = len([r for r in all_requests if r.status in ("REJECTED", "REPLANNING")])
    published = len([r for r in all_requests if r.status == "PUBLISHED"])
    failed = len([r for r in all_requests if r.status == "FAILED"])

    return {
        "stats": {
            "total_requests": total,
            "pending": pending,
            "ai_processing": ai_processing,
            "awaiting_approval": awaiting,
            "approved": approved,
            "rejected": rejected,
            "published": published,
            "failed": failed,
        },
        "recent_requests": [
            {
                "id": r.id,
                "department": r.department,
                "maintenance_type": r.maintenance_type,
                "section": r.section,
                "priority": r.priority,
                "requested_date": r.requested_date,
                "status": r.status,
                "current_version": max([p.version for p in db.query(BlockPlan).filter(BlockPlan.request_id == r.id).all()], default=0),
                "latest_plan": _latest_plan_dict(db, r.id),
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in sorted(all_requests, key=lambda x: x.created_at or "", reverse=True)[:20]
        ],
    }


@router.get("/officer")
def officer_dashboard(db: Session = Depends(get_db), user: User = Depends(require_officer)):
    all_requests = db.query(MaintenanceRequest).all()
    pending = [r for r in all_requests if r.status in ("REPORT_READY", "AWAITING_OFFICER")]
    high_risk = [r for r in all_requests if r.status == "AWAITING_OFFICER"]
    replanning = [r for r in all_requests if r.status in ("REPLANNING", "REJECTED")]
    approved = [r for r in all_requests if r.status == "APPROVED"]
    published = [r for r in all_requests if r.status == "PUBLISHED"]

    return {
        "stats": {
            "pending_approvals": len(pending),
            "high_risk": len(high_risk),
            "replanning": len(replanning),
            "approved_today": len(approved),
            "published_blocks": len(published),
        },
        "pending_requests": [
            {
                "id": r.id,
                "engineer_id": r.engineer_id,
                "department": r.department,
                "maintenance_type": r.maintenance_type,
                "section": r.section,
                "priority": r.priority,
                "status": r.status,
                "requested_date": r.requested_date,
                "preferred_start": r.preferred_start,
                "preferred_end": r.preferred_end,
                "duration_minutes": r.duration_minutes,
                "engineer_name": _engineer_name(db, r.engineer_id),
                "current_version": max([p.version for p in db.query(BlockPlan).filter(BlockPlan.request_id == r.id).all()], default=0),
                "latest_plan": _latest_plan_dict(db, r.id),
            }
            for r in pending
        ],
    }


def _engineer_name(db, engineer_id):
    if not engineer_id:
        return "Unknown"
    user = db.query(User).filter(User.id == engineer_id).first()
    return user.name if user else "Unknown"


def _latest_plan_dict(db, request_id):
    plan = (
        db.query(BlockPlan)
        .filter(BlockPlan.request_id == request_id)
        .order_by(BlockPlan.version.desc())
        .first()
    )
    if not plan:
        return None
    return {
        "id": plan.id,
        "version": plan.version,
        "start_time": plan.start_time,
        "end_time": plan.end_time,
        "duration_minutes": plan.duration_minutes,
        "risk_score": plan.risk_score,
        "confidence": plan.confidence,
        "estimated_delay_minutes": plan.estimated_delay_minutes,
        "affected_trains": plan.affected_trains,
        "status": plan.status,
        "block_id": plan.block_id,
    }
