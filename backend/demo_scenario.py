"""RailSync AI - Automated end-to-end demo scenario test.

Replicates the SIH 2026 demo: Engineer submits a maintenance request,
the AI agent pipeline generates Plan V1, the Officer rejects it (reason
required), replanning produces V2 honoring the officer's constraint,
and the Officer approves -> block published. Runs against a live backend.

Usage:  python demo_scenario.py   (backend must be running on :8000)
Exit code 0 = PASS, 1 = FAIL.
"""
import sys
import time
import urllib.request
import urllib.error
import json

BASE = "http://localhost:8000"
PASS = 0
FAIL = 1

ENGINEER = {"email": "engineer@railsync.in", "password": "engineer123"}
OFFICER = {"email": "officer@railsync.in", "password": "officer123"}


def api(method, path, token=None, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def login(cred):
    st, js = api("POST", "/api/auth/login", body=cred)
    assert st == 200, f"login failed: {st} {js}"
    return js["access_token"]


def wait_status(token, rid, target, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        st, pl = api("GET", f"/api/requests/{rid}", token=token)
        if st == 200 and pl.get("status") == target:
            return pl
        time.sleep(2)
    raise AssertionError(f"Request {rid} never reached {target}")


def main():
    checks = []

    def check(name, cond):
        checks.append((name, cond))
        print(("  [PASS] " if cond else "  [FAIL] ") + name)
        return cond

    print("=== RailSync AI Demo Scenario ===")

    et = login(ENGINEER)
    print("1. Engineer logged in")

    body = {
        "department": "Electrical",
        "maintenance_type": "Track Replacement",
        "location": "Shivajinagar",
        "section": "Shivajinagar - Khadki",
        "requested_date": "2026-09-05",
        "preferred_start": "10:00",
        "preferred_end": "14:00",
        "duration_minutes": 120,
        "priority": "HIGH",
        "description": "Wear on turnout 42; urgent rail replacement required",
    }
    st, created = api("POST", "/api/requests", token=et, body=body)
    assert st == 200, f"create failed {st} {created}"
    rid = created["id"]
    print(f"2. Request MR-{rid} created ({created['status']})")

    st, _ = api("POST", f"/api/requests/{rid}/analyze", token=et)
    check("3. AI analysis started", st == 200)
    print(f"   analyze status: {st}")

    wait_status(et, rid, "REPORT_READY")
    st, plans = api("GET", f"/api/requests/{rid}/plans", token=et)
    v1 = next(p for p in plans if p["version"] == 1)
    print(f"4. Plan V1 generated: {v1['start_time']}-{v1['end_time']} (score={v1['score']})")
    check("   V1 produced after AI pipeline", v1["status"] == "PENDING_REVIEW")

    ot = login(OFFICER)
    st, pending_resp = api("GET", "/api/officer/pending", token=ot)
    pending_items = pending_resp.get("pending", [])
    check("5. Officer sees pending request", any(p["id"] == rid for p in pending_items))
    print(f"   pending count: {len(pending_items)}")

    plan1 = v1["id"]

    st, js = api("POST", f"/api/plans/{plan1}/reject", token=ot, body={"rejection_reason": "  "})
    check("6. Reject WITHOUT reason -> HTTP 400", st == 400)
    print(f"   got {st}: {js.get('detail', js)}")

    st, js = api("POST", f"/api/plans/{plan1}/reject", token=ot, body={
        "rejection_reason": "Important passenger train affected. Avoid 10:00-13:00.",
        "avoid_time": "10:00-13:00",
    })
    check("7. Reject WITH reason -> replanning auto-initiated (V2)", st == 200 and js.get("new_version") == 2)
    print(f"   got {st}, new_version: {js.get('new_version')}")

    wait_status(et, rid, "REPORT_READY")
    st, plans = api("GET", f"/api/requests/{rid}/plans", token=et)
    v2 = next(p for p in plans if p["version"] == 2)
    v2_start = v2["start_time"]
    print(f"8. Plan V2 generated: {v2_start}-{v2['end_time']}")
    in_avoid = "10:00" <= v2_start < "13:00"
    check("   V2 respects officer 'avoid 10:00-13:00'", not in_avoid and v2["status"] == "PENDING_REVIEW")

    st, js = api("POST", f"/api/plans/{v2['id']}/approve", token=ot)
    check("9. Officer approves V2 -> published", st == 200 and js.get("version") == 2)
    print(f"    block: {js.get('block_id')}, version: {js.get('version')}")

    st, hist = api("GET", f"/api/requests/{rid}/history", token=et)
    vers = {h["version"]: h["status"] for h in hist.get("plans", [])}
    check("10. Version history intact (V1 rejected, V2 approved)",
          vers.get(1) == "REJECTED" and vers.get(2) == "APPROVED")
    print(f"    history: {vers}")

    failed = [n for n, c in checks if not c]
    print("\n" + "=" * 40)
    print(f"RESULT: {'FAIL' if failed else 'PASS'} ({sum(c for _, c in checks)}/{len(checks)} checks)")
    return FAIL if failed else PASS


if __name__ == "__main__":
    sys.exit(main())
