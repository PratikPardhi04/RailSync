from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.models import Train, BlockPlan, BlockExecution, LiveSimState, MaintenanceRequest


PREMIUM = ("RAJDHANI", "SHATABDI", "VANDE_BHARAT")
APPROVED_STATUSES = ("APPROVED", "PUBLISHED")


def minutes_of_day(t: str) -> int:
    if not t:
        return 0
    try:
        parts = t.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return 0


def fmt_minutes(m: int) -> str:
    m = m % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def _jitter(train_number: str) -> int:
    total = sum(ord(c) for c in train_number)
    return (total * 7) % 9


def get_or_create_state(db: Session) -> LiveSimState:
    state = db.query(LiveSimState).filter(LiveSimState.id == 1).first()
    if not state:
        default_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        state = LiveSimState(
            id=1,
            sim_date=default_date,
            sim_minutes=5 * 60 + 30,
            speed=30,
            running="true",
            last_tick_at=datetime.utcnow(),
        )
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def advance(db: Session):
    """Lazily advance the simulated clock based on real elapsed time * speed."""
    state = get_or_create_state(db)
    if state.running != "true":
        return state
    now = datetime.utcnow()
    last = state.last_tick_at or now
    elapsed_sec = max(0.0, min((now - last).total_seconds(), 300.0))
    delta_min = int(round(elapsed_sec * state.speed / 60.0))
    if delta_min > 0:
        state.sim_minutes = state.sim_minutes + delta_min
        state.last_tick_at = now
        db.commit()
    return state


def _active_block_windows(db: Session) -> list:
    """Return sanctioned/active execution windows keyed by section."""
    executions = db.query(BlockExecution).all()
    result = []
    for ex in executions:
        plan = db.query(BlockPlan).filter(BlockPlan.id == ex.plan_id).first()
        if not plan or plan.status not in APPROVED_STATUSES:
            continue
        req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == plan.request_id).first()
        start = minutes_of_day(plan.start_time)
        end = minutes_of_day(plan.end_time)
        result.append({
            "block_id": ex.block_id or plan.block_id,
            "plan_id": plan.id,
            "version": plan.version,
            "section": req.section if req else "",
            "start": start,
            "end": end,
            "exec_status": ex.status,
            "date": plan.proposed_date,
        })
    return result


def _train_snapshots(db: Session, sim_date: str, sim_minutes: int, windows: list) -> list:
    trains = db.query(Train).order_by(Train.arrival_time).all()
    snapshots = []
    for t in trains:
        arr = minutes_of_day(t.arrival_time)
        dep = minutes_of_day(t.departure_time)
        if dep < arr:
            dep = arr + 5
        jitter = _jitter(t.train_number)

        delay = 0
        held_by = None
        for w in windows:
            if w.get("section", "").lower() in (t.section or "").lower() or not w.get("section"):
                if w["start"] <= arr < w["end"] or w["start"] < arr + jitter < w["end"]:
                    if w["exec_status"] in ("BLOCK_ACTIVE",):
                        delay += w["end"] - max(arr, min(arr + jitter, w["start"]))
                        held_by = w.get("block_id")
                    elif w["exec_status"] in ("SANCTIONED", "IN_POSITION") and arr < w["end"]:
                        delay += max(0, w["end"] - max(arr, w["start"]))
                        held_by = w.get("block_id") if held_by is None else held_by

        eff_arr = arr + jitter + delay

        if sim_minutes < arr - 20:
            status = "NOT_DUE"
            position = 0.0
        elif sim_minutes < eff_arr:
            span = max(20.0, eff_arr - (arr - 20))
            status = "APPROACHING"
            position = min(0.99, (sim_minutes - (arr - 20)) / span)
        elif sim_minutes < eff_arr + (dep - arr):
            span = max(5.0, (dep - arr))
            status = "IN_SECTION"
            position = min(0.99, (sim_minutes - eff_arr) / span)
        else:
            status = "DEPARTED"
            position = 1.0

        actual_delay = jitter + delay if status != "NOT_DUE" else 0
        snapshots.append({
            "train_number": t.train_number,
            "train_name": t.train_name,
            "train_type": t.train_type,
            "priority": t.priority,
            "origin": t.origin,
            "destination": t.destination,
            "section": t.section,
            "scheduled_arrival": t.arrival_time,
            "scheduled_departure": t.departure_time,
            "projected_arrival": fmt_minutes(eff_arr),
            "status": status,
            "position": round(position, 3),
            "delay_minutes": actual_delay,
            "held_by": held_by,
            "premium": t.priority in PREMIUM,
        })
    return snapshots


def _block_snapshots(db: Session, sim_date: str, sim_minutes: int) -> list:
    executions = db.query(BlockExecution).all()
    blocks = []
    for ex in executions:
        plan = db.query(BlockPlan).filter(BlockPlan.id == ex.plan_id).first()
        if not plan or plan.status not in APPROVED_STATUSES:
            continue
        req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == plan.request_id).first()
        start = minutes_of_day(plan.start_time)
        end = minutes_of_day(plan.end_time)
        live = "ACTIVE" if (ex.status == "BLOCK_ACTIVE" and start <= sim_minutes < end) else (
            "UPCOMING" if sim_minutes < start else ("EXPIRED" if sim_minutes >= end else "LIVE")
        )
        blocks.append({
            "block_id": ex.block_id or plan.block_id,
            "plan_id": plan.id,
            "version": plan.version,
            "section": req.section if req else "",
            "maintenance_type": req.maintenance_type if req else "",
            "window": f"{plan.start_time}-{plan.end_time}",
            "start": plan.start_time,
            "end": plan.end_time,
            "status": ex.status,
            "live_phase": live,
            "active_now": ex.status == "BLOCK_ACTIVE" and start <= sim_minutes < end,
        })
    return blocks


def _conflicts(db: Session, sim_minutes: int, snapshots: list, windows: list) -> list:
    conflicts = []
    for s in snapshots:
        if not s["premium"]:
            continue
        proj_arr = minutes_of_day(s["projected_arrival"])
        for w in windows:
            if w["section"] and w["section"].lower() != (s["section"] or "").lower():
                continue
            if w["end"] <= proj_arr and proj_arr is not None:
                pass
            if w["start"] <= proj_arr < w["end"]:
                if w["exec_status"] in ("SANCTIONED", "IN_POSITION", "BLOCK_ACTIVE") and not (w["exec_status"] == "BLOCK_ACTIVE" and sim_minutes >= w["end"]):
                    conflicts.append({
                        "train_number": s["train_number"],
                        "train_name": s["train_name"],
                        "priority": s["priority"],
                        "block_id": w["block_id"],
                        "plan_id": w["plan_id"],
                        "window": fmt_minutes(w["start"]) + "-" + fmt_minutes(w["end"]),
                        "projected_arrival": s["projected_arrival"],
                        "delay_minutes": s["delay_minutes"],
                        "severity": "HIGH" if w["end"] - proj_arr < 10 else "MEDIUM",
                        "auto_resolvable": w["exec_status"] in ("SANCTIONED", "IN_POSITION"),
                    })
    return conflicts


def _events(db: Session, sim_minutes: int) -> list:
    events = []
    executions = db.query(BlockExecution).all()
    for ex in executions:
        if ex.sanctioned_at:
            events.append({
                "time": ex.sanctioned_at.strftime("%H:%M"),
                "kind": "SANCTIONED",
                "text": f"Block {ex.block_id} sanctioned for maintenance",
            })

    trains = db.query(Train).order_by(Train.arrival_time).all()
    for t in trains:
        jitter = _jitter(t.train_number)
        if jitter >= 5 and t.priority in PREMIUM:
            arr = minutes_of_day(t.arrival_time)
            if abs(sim_minutes - arr) < 15:
                delta = jitter
                if delta >= 5:
                    events.append({
                        "time": fmt_minutes(min(sim_minutes, arr)),
                        "kind": "LATE_RUNNING",
                        "text": f"{t.train_name} running approx +{delta} min on {t.section}",
                    })
    return events[-25:]


def snapshot(db: Session) -> dict:
    state = advance(db)
    sim_date = state.sim_date
    sim_minutes = state.sim_minutes
    windows = _active_block_windows(db)
    trains = _train_snapshots(db, sim_date, sim_minutes, windows)
    blocks = _block_snapshots(db, sim_date, sim_minutes)
    conflicts = _conflicts(db, sim_minutes, trains, windows)
    events = _events(db, sim_minutes)
    return {
        "sim_date": sim_date,
        "sim_time": fmt_minutes(sim_minutes),
        "sim_minutes": sim_minutes,
        "speed": state.speed,
        "running": state.running == "true",
        "trains": trains,
        "blocks": blocks,
        "conflicts": conflicts,
        "events": events,
    }


def set_speed(db: Session, speed: int):
    speed = max(1, min(600, int(speed)))
    state = advance(db)
    state.speed = speed
    state.last_tick_at = datetime.utcnow()
    db.commit()
    return state.speed


def set_running(db: Session, running: bool):
    state = advance(db)
    state.running = "true" if running else "false"
    state.last_tick_at = datetime.utcnow()
    db.commit()
    return state.running == "true"