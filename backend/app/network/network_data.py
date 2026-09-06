"""Railway network / topology reference data.

This is the source of truth for route feasibility. The Alternative Routing
agent may ONLY propose a DIVERT action whose route_id exists here - the LLM is
never allowed to invent a route. The deterministic Route & Operations Optimizer
validates every action against this data before accepting it.
"""
from typing import Dict, List, Optional

# Section-id -> diversion / alternate routes available in the (prototype) network.
# `congested_at_peak` flags routes whose spare capacity is already committed.
ALTERNATE_ROUTES: Dict[str, List[Dict]] = {
    "Shivajinagar - Khadki": [
        {
            "id": "ALT-SK-1",
            "name": "Via Yerwada (main line diversion)",
            "path": "Shivajinagar - Yerwada - Khadki",
            "add_minutes": 18,
            "spare_capacity": True,
            "congested_at_peak": False,
            "compatible_priorities": ["RAJDHANI", "SHATABDI", "VANDE_BHARAT", "EXPRESS", "SUPERFAST"],
            "electrified": True,
            "notes": "Preferred diversion for passenger services.",
        },
        {
            "id": "ALT-SK-2",
            "name": "Via Hadapsar loop line",
            "path": "Shivajinagar - Hadapsar - Khadki",
            "add_minutes": 32,
            "spare_capacity": False,
            "congested_at_peak": True,
            "compatible_priorities": ["EXPRESS", "SUPERFAST", "PASSENGER", "FREIGHT"],
            "electrified": True,
            "notes": "Longer loop; freight pre-booked during peak hours.",
        },
    ],
    "Pune - Lonavala": [
        {
            "id": "ALT-PL-1",
            "name": "Via Khadki - Pimpri - Kanhe (berg ghat relief)",
            "path": "Pune - Khadki - Pimpri - Kanhe - Lonavala",
            "add_minutes": 25,
            "spare_capacity": True,
            "congested_at_peak": False,
            "compatible_priorities": ["RAJDHANI", "SHATABDI", "VANDE_BHARAT", "EXPRESS", "SUPERFAST"],
            "electrified": True,
            "notes": "Used during ghat line possessions.",
        },
    ],
    "Shivajinagar - Hadapsar": [
        {
            "id": "ALT-SH-1",
            "name": "Via Yerwada junction",
            "path": "Shivajinagar - Yerwada - Hadapsar",
            "add_minutes": 21,
            "spare_capacity": True,
            "congested_at_peak": False,
            "compatible_priorities": ["RAJDHANI", "SHATABDI", "VANDE_BHARAT", "EXPRESS", "SUPERFAST", "PASSENGER"],
            "electrified": True,
            "notes": "Standard diversion for suburban flows.",
        },
    ],
}

# Fallback route any section can use as last resort.
FALLBACK_ROUTE: Dict = {
    "id": "ALT-GEN-1",
    "name": "Perimeter goods loop",
    "path": "via adjacent goods loop",
    "add_minutes": 40,
    "spare_capacity": True,
    "congested_at_peak": False,
    "compatible_priorities": ["FREIGHT", "PASSENGER"],
    "electrified": True,
    "notes": "Last-resort diversion; freight/passenger only.",
}


def alternate_routes_for(section: str) -> List[Dict]:
    """Return candidate diversions for a section (network truth)."""
    routes = list(ALTERNATE_ROUTES.get(section or "", []))
    if not routes:
        routes = [dict(FALLBACK_ROUTE)]
    return routes


def route_exists(section: str, route_id: str) -> bool:
    if not route_id:
        return False
    return any(r["id"] == route_id for r in alternate_routes_for(section))


def route_details(section: str, route_id: str) -> Optional[Dict]:
    for r in alternate_routes_for(section):
        if r["id"] == route_id:
            return r
    return None


def is_route_available(section: str, route_id: str, at_peak: bool = False) -> bool:
    """Deterministic availability check (capacity-aware)."""
    r = route_details(section, route_id)
    if not r:
        return False
    if at_peak and r.get("congested_at_peak"):
        return False
    return bool(r.get("spare_capacity", True))


def compatible_with_route(priority: str, section: str, route_id: str) -> bool:
    r = route_details(section, route_id)
    if not r:
        return False
    compatible = [p.upper() for p in r.get("compatible_priorities", [])]
    return str(priority).upper() in compatible


def network_sections() -> List[str]:
    return list(ALTERNATE_ROUTES.keys())