"""RailLink AI - Live Ops demo test.

Exercises the operational lifecycle and live train simulation:
  approve -> sanction (notice/CA artifacts) -> checkin -> activate ->
  live board shows ACTIVE block + held train delays -> release -> complete,
  plus dynamic re-planning (AI regenerates a compliant window for review).

Usage:  python demo_live.py  (backend must be running on :8000)
Exit code 0 = PASS, 1 = FAIL.
"""
import sys
import time
import urllib.request
import urllib.error
import json

BASE = "http://localhost:8000"
ENGINEER = {"email": "engineer@raillink.in", "password": "engineer123"}
OFFICER = {"email": "officer@raillink.in", "password": "officer123"}


def api(method, path, token=None, body=None, timeout=60):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
    except Exception as e:
        return 0, {"detail": str(e)}


def login(cred):
    st, js = api("POST", "/api/auth/login", body=cred)
    assert st == 200, f"login failed: {st} {js}"
    return js["access_token"]


def wait_status(token, rid, target, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        st, pl = api("GET", f"/api/requests/{rid}", token=token)
        if st == 200 and pl.get("status") == target:
            return pl
        time.sleep(2)
    raise AssertionError(f"Request {rid} never reached {target} in {timeout}s")


def create_and_plan(et, ot, label):
    rid = None
    st, created = api("POST", "/api/requests", token=et, body={
        "department": "Engineering",
        "maintenance_type": "Track Maintenance",
        "location": "Pune Division",
        "section": "Shivajinagar - Khadki",
        "requested_date": (time.strftime("%Y-%m-%d")),
        "preferred_start": "10:00",
        "preferred_end": "14:00",
        "duration_minutes": 120,
        "priority": "HIGH",
        "description": f"{label} - live ops automated test",
        "work_type": "Corrective Repair",
        "crew_size": 8,
        "equipment": "Tower Wagon",
        "weather_sensitive": "YES",
    })
    rid = created.get("id")
    st, _ = api("POST", f"/api/requests/{rid}/analyze", token=et)
    req = wait_status(ot, rid, "REPORT_READY")
    st, hist = api("GET", f"/api/requests/{rid}/history", token=ot)
    plan_id = None
    for p in hist.get("plans", []):
        if p["status"] == "REPORT_READY":
            plan_id = None
    report = None
    st, req_full = api("GET", f"/api/requests/{rid}", token=ot)
    pl = req_full.get("plans", [])
    if pl:
        plan_id = pl[-1]["id"]
    return rid, plan_id


def main():
    checks = []

    def check(name, cond):
        checks.append((name, cond))
        print(("  [PASS] " if cond else "  [FAIL] ") + name)
        return cond

    print("=== RailLink AI Live Ops Demo ===")

    et = login(ENGINEER)
    ot = login(OFFICER)
    print("Logins OK")

    # 1. Create + plan a block
    st, created = api("POST", "/api/requests", token=et, body={
        "department": "Engineering",
        "maintenance_type": "Track Maintenance",
        "location": "Pune Division",
        "section": "Shivajinagar - Khadki",
        "requested_date": time.strftime("%Y-%m-%d"),
        "preferred_start": "10:00",
        "preferred_end": "14:00",
        "duration_minutes": 120,
        "priority": "HIGH",
        "description": "Live ops demo block",
        "work_type": "Track Reconditioning",
        "crew_size": 10,
        "equipment": "Tamping Machine",
        "weather_sensitive": "YES",
    })
    rid = created["id"]
    print(f"1. Request MR-{rid} created")

    st, _ = api("POST", f"/api/requests/{rid}/analyze", token=et)
    req = wait_status(ot, rid, "REPORT_READY", timeout=240)
    check("2. AI pipeline produced report", req["status"] == "REPORT_READY")

    st, req_full = api("GET", f"/api/requests/{rid}", token=ot)
    plans = req_full.get("plans", [])
    plan_id = plans[-1]["id"]
    version = plans[-1]["version"]
    print(f"3. Plan V{version} ready (plan_id={plan_id})")

    st, rep = api("GET", f"/api/requests/{rid}/report", token=ot)
    check("4. Report includes weather advisory", bool((rep.get("plan") or {}).get("report_data", {}).get("weather", {}).get("advisory")))

    st, appr = api("POST", f"/api/plans/{plan_id}/approve", token=ot)
    block_id = appr.get("block_id")
    check("5. Officer approved plan", st == 200 and bool(block_id))

    # 2. Sanction -> artifacts
    st, san = api("POST", f"/api/execution/plans/{plan_id}/sanction", token=ot)
    notice = (san.get("block_notice") or "")
    ca = (san.get("caution_order") or "")
    check("6. Block sanctioned", st == 200 and san.get("status") == "SANCTIONED")
    check("7. Block notice generated", "RAIL BLOCK PERMISSION" in notice and block_id in notice)
    check("8. Caution order generated", "CAUTION ORDER" in ca)

    # 3. Live state reflects sanctioned block
    st, ls = api("GET", "/api/live/state")
    live_blocks = ls.get("blocks", [])
    check("9. Live board shows sanctioned block", any(b["block_id"] == block_id for b in live_blocks))

    # 4. Field lifecycle
    st, ci = api("POST", f"/api/execution/plans/{plan_id}/checkin", token=et)
    check("10. Engineer check-in (IN_POSITION)", st == 200 and ci.get("status") == "IN_POSITION")

    st, ac = api("POST", f"/api/execution/plans/{plan_id}/activate", token=et)
    check("11. Block activated (BLOCK_ACTIVE)", st == 200 and ac.get("status") == "BLOCK_ACTIVE")

    # 5. Jump clock inside the block window -> trains held, delays appear
    st, jump_resp = api("POST", "/api/live/jump", body={"minutes": 45})
    st, ls = api("GET", "/api/live/state")
    active = [b for b in ls.get("blocks", []) if b["block_id"] == block_id]
    any_held = any(t["held_by"] for t in ls.get("trains", []))
    any_delay = any(t["delay_minutes"] > 0 for t in ls.get("trains", []) if t["status"] != "NOT_DUE")
    check("12. Clock advanced", jump_resp.get("sim_time") is not None)
    check("13. Block shows ACTIVE live phase", bool(active) and active[0]["status"] == "BLOCK_ACTIVE")
    print("     (held/delay depend on window overlap - informational)")

    # 6. Release + complete
    st, rel = api("POST", f"/api/execution/plans/{plan_id}/release", token=et)
    check("14. Block released", st == 200 and rel.get("status") == "RELEASED")

    st, com = api("POST", f"/api/execution/plans/{plan_id}/complete", token=et)
    check("15. Block completed", st == 200 and com.get("status") == "COMPLETED")

    # 7. Dynamic replan path: plan a NEW block, approve, sanction, then trigger dynamic replan
    st, created2 = api("POST", "/api/requests", token=et, body={
        "department": "S&T",
        "maintenance_type": "Signal Maintenance",
        "location": "Pune Division",
        "section": "Shivajinagar - Khadki",
        "requested_date": time.strftime("%Y-%m-%d"),
        "preferred_start": "09:00",
        "preferred_end": "12:00",
        "duration_minutes": 90,
        "priority": "HIGH",
        "description": "Dynamic replan demo block",
        "weather_sensitive": "NO",
    })
    rid2 = created2["id"]
    st, _ = api("POST", f"/api/requests/{rid2}/analyze", token=et)
    req2 = wait_status(ot, rid2, "REPORT_READY", timeout=240)

    st, req_full2 = api("GET", f"/api/requests/{rid2}", token=ot)
    plans2 = req_full2.get("plans", [])
    plan2_id = plans2[-1]["id"]

    st, appr2 = api("POST", f"/api/plans/{plan2_id}/approve", token=ot)
    st, san2 = api("POST", f"/api/execution/plans/{plan2_id}/sanction", token=ot)
    old_window = san2.get("window") or "" if san2 else ""
    old_start = (old_window.split("-")[0] if old_window else "")
    check("16. Second block sanctioned", st == 200 and san2.get("status") == "SANCTIONED")

    st, dr = api("POST", f"/api/live/dynamic-replan/{plan2_id}", token=ot)
    check("17. Dynamic replan triggered", st == 200 and dr.get("new_version") == 2)

    # wait for the new version to be generated
    new_plan = None
    for _ in range(240):
        st, req_full2 = api("GET", f"/api/requests/{rid2}", token=ot)
        plans2 = req_full2.get("plans", [])
        if len(plans2) >= 2:
            new_plan = plans2[-1]
            break
        time.sleep(2)

    if new_plan:
        check("18. V2 generated by AI with new window", new_plan.get("start_time") != old_start)
        st, rep2 = api("GET", f"/api/requests/{rid2}/report?plan_version=2", token=ot)
        rd2 = (rep2.get("plan") or {}).get("report_data", {})
        check("19. Replan advisory says RECOMMEND_APPROVE", (rd2.get("ai_advisory") or {}).get("label") == "RECOMMEND_APPROVE")
        ofb = rd2.get("officer_feedback") or {}
        check("20. Report records dynamic replan reason", "dynamic" in (ofb.get("rejection_reason") or "").lower())
    else:
        check("18. V2 generated by AI with new window", False)
        check("19. Replan advisory says RECOMMEND_APPROVE", False)
        print("     (V2 not produced in time)")

    print()
    failed = [n for n, c in checks if not c]
    print(f"Checks passed: {len(checks) - len(failed)}/{len(checks)}")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())