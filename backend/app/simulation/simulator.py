import time
from typing import Dict, Any, List

from app.schemas.workflow import TrainImpact


def run(
    selected_window: Dict[str, Any],
    trains: List[Dict[str, Any]],
    request: Dict[str, Any],
) -> TrainImpact:
    start = time.time()
    block_start = _to_minutes(selected_window.get("start_time", "10:00"))
    block_end = _to_minutes(selected_window.get("end_time", "12:00"))
    section = request.get("section", "")

    affected_trains = []
    total_delay = 0
    max_delay = 0

    for train in trains:
        if section and section.lower() not in train.get("section", "").lower():
            continue

        arr = _to_minutes(train.get("arrival_time", "00:00"))
        dep = _to_minutes(train.get("departure_time", "00:00"))
        if dep < arr:
            dep += 24 * 60

        if arr < block_end and dep > block_start:
            delay = _calculate_delay(train, block_start, block_end, arr)
            holding = delay > 15
            rerouting = delay > 30

            affected_trains.append({
                "train_number": train["train_number"],
                "train_name": train["train_name"],
                "train_type": train["train_type"],
                "priority": train.get("priority", "PASSENGER"),
                "scheduled_arrival": train.get("arrival_time", "00:00"),
                "scheduled_departure": train.get("departure_time", "00:00"),
                "delay_minutes": round(delay, 1),
                "action": "REROUTE" if rerouting else "HOLD" if holding else "DELAY",
                "status": "rerouted" if rerouting else "held" if holding else "delayed",
            })
            total_delay += delay
            max_delay = max(max_delay, delay)

    rerouted = sum(1 for t in affected_trains if t["action"] == "REROUTE")
    held = sum(1 for t in affected_trains if t["action"] == "HOLD")
    delayed_only = sum(1 for t in affected_trains if t["action"] == "DELAY")

    return TrainImpact(
        affected_trains=affected_trains,
        total_trains_affected=len(affected_trains),
        total_delay_minutes=round(total_delay, 1),
        max_delay_minutes=round(max_delay, 1),
        trains_rerouted=rerouted,
        trains_held=held,
        trains_delayed=delayed_only,
        simulation_block={
            "start": selected_window.get("start_time", "10:00"),
            "end": selected_window.get("end_time", "12:00"),
        },
        summary=(
            f"Simulation: {len(affected_trains)} trains affected. "
            f"Total delay: {round(total_delay, 1)} min. "
            f"Max delay: {round(max_delay, 1)} min. "
            f"Rerouted: {rerouted}, Held: {held}, Delayed: {delayed_only}."
        ),
        execution_time=round(time.time() - start, 3),
    )


def _to_minutes(time_str: str) -> int:
    parts = time_str.strip().split(":")
    return int(parts[0]) * 60 + int(parts[1])


# Congestion-aware delay model for a busy corridor. `base` is the standing
# operational handling time for the train class; the wait until the block
# clears dominates - a train caught inside a busy window realistically delays
# far more than the old (wait * 0.15) rule, which is what makes HOLD/REROUTE
# behaviour (and therefore DIVERT proposals) appear on congested sections.
_PRIORITY_BASE = {
    "RAJDHANI": 15, "SHATABDI": 13, "VANDE_BHARAT": 14, "SUPERFAST": 11,
    "EXPRESS": 10, "PASSENGER": 8, "FREIGHT": 6,
}
_WAIT_FACTOR = 0.4


def _calculate_delay(train: Dict[str, Any], block_start: int, block_end: int, arr: int) -> float:
    base = _PRIORITY_BASE.get(train.get("priority", "PASSENGER"), 8)
    dep = _to_minutes(train.get("departure_time", "00:00"))
    if dep < arr:
        dep += 24 * 60

    if arr >= block_start and arr < block_end:
        # Train arrives during the block - it must wait until the block clears.
        wait = block_end - arr
    elif arr < block_start and dep > block_start:
        # Train is queued just ahead of the block and departs into it.
        wait = dep - block_start
    else:
        wait = 0

    if wait <= 0:
        return base
    return round(base + wait * _WAIT_FACTOR, 1)
