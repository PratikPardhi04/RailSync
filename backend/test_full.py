import sys
import os
import time
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def api(method, path, body=None, token=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()}
    except Exception as e:
        return {"error": str(e)}


# Start server if not running
print("=== HEALTH CHECK ===")
health = api("GET", "/api/health")
print("Health:", health)

print("\n=== 1. LOGIN AS ENGINEER ===")
login = api("POST", "/api/auth/login", {"email": "engineer@railsync.in", "password": "engineer123"})
if "access_token" not in login:
    print("LOGIN FAILED:", login)
    sys.exit(1)
token = login["access_token"]
print("Engineer logged in:", login["user"]["name"], login["user"]["role"])

print("\n=== 2. CREATE MAINTENANCE REQUEST ===")
req_data = {
    "department": "Engineering",
    "maintenance_type": "Track Maintenance",
    "location": "Pune Division",
    "section": "Shivajinagar - Khadki",
    "requested_date": "2026-09-04",
    "preferred_start": "10:00",
    "preferred_end": "14:00",
    "duration_minutes": 120,
    "priority": "HIGH",
    "description": "Scheduled track inspection and maintenance on mainline section",
}
created = api("POST", "/api/requests", req_data, token)
print("Created:", created)
request_id = created["id"]

print("\n=== 3. START AI ANALYSIS ===")
analyze = api("POST", f"/api/requests/{request_id}/analyze", None, token)
print("Analyze:", analyze)

print("\n=== 4. WAIT FOR ANALYSIS ===")
time.sleep(15)
req_detail = api("GET", f"/api/requests/{request_id}", token=token)
print("Status:", req_detail.get("status"))
print("Plans:", len(req_detail.get("plans", [])))
if req_detail.get("plans"):
    p = req_detail["plans"][0]
    print(f"  V{p['version']}: {p['start_time']}-{p['end_time']}, affected={len(p['affected_trains'] or [])}, delay={p['estimated_delay_minutes']}")

print("\n=== 5. GET AGENT RESULTS ===")
agents = api("GET", f"/api/requests/{request_id}/agents", token=token)
print("Agent results:", len(agents) if isinstance(agents, list) else agents)
if isinstance(agents, list):
    for a in agents:
        print(f"  {a['agent_name']}: {a['status']}")

print("\n=== 6. GET REPORT ===")
report = api("GET", f"/api/requests/{request_id}/report", token=token)
if "plan" in report:
    print(f"Plan V{report['plan']['version']}: {report['plan']['start_time']}-{report['plan']['end_time']}")
else:
    print("No report:", report)

print("\n=== 7. LOGIN AS OFFICER ===")
officer_login = api("POST", "/api/auth/login", {"email": "officer@railsync.in", "password": "officer123"})
officer_token = officer_login["access_token"]
print("Officer logged in:", officer_login["user"]["name"], officer_login["user"]["role"])

print("\n=== 8. OFFICER PENDING ===")
pending = api("GET", "/api/officer/pending", token=officer_token)
print("Pending:", len(pending.get("pending", [])))
if pending.get("pending"):
    for req in pending["pending"]:
        print(f"  MR-{req['id']}: {req['section']} {req['status']} V{req.get('current_version')}")

print("\n=== 9. REJECT THE PLAN (NO REASON - SHOULD FAIL) ===")
plan_id = None
if req_detail.get("plans"):
    plan_id = req_detail["plans"][0]["id"]
if plan_id:
    try:
        import urllib.error
        url = BASE + f"/api/plans/{plan_id}/reject"
        bod = json.dumps({"rejection_reason": ""}).encode()
        rq = urllib.request.Request(url, data=bod, headers={"Content-Type": "application/json", "Authorization": f"Bearer {officer_token}"}, method="POST")
        with urllib.request.urlopen(rq) as resp:
            print("Reject (empty reason) succeeded (should not happen):", resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Reject empty reason correctly failed: HTTP {e.code}")

print("\n=== 10. REJECT THE PLAN (WITH REASON) ===")
if plan_id:
    reject = api("POST", f"/api/plans/{plan_id}/reject", {
        "rejection_reason": "Important passenger train affected. Avoid 10:00-13:00",
        "avoid_time": "10:00-13:00",
    }, officer_token)
    print("Reject:", reject)
    print("  Rejection auto-triggers replanning (V2) in the background...")
    time.sleep(15)
    req_detail2 = api("GET", f"/api/requests/{request_id}", token=officer_token)
    print("After replan status:", req_detail2.get("status"))
    print("Plans after replan:", len(req_detail2.get("plans", [])))
    for ps in req_detail2.get("plans", []):
        print(f"  V{ps['version']}: {ps['start_time']}-{ps['end_time']}, status={ps['status']}")

    print("\n=== 11. APPROVE LATEST PLAN ===")
    latest = None
    if req_detail2.get("plans"):
        latest = max(req_detail2["plans"], key=lambda x: x["version"])
    if latest:
        approve = api("POST", f"/api/plans/{latest['id']}/approve", None, officer_token)
        print("Approve:", approve)

print("\n=== 12. GET HISTORY ===")
history = api("GET", f"/api/requests/{request_id}/history", token=officer_token)
print("History plans:", len(history.get("plans", [])))
for h in history.get("plans", []):
    print(f"  V{h['version']}: {h['start_time']}-{h['end_time']} {h['status']}")
print("Audit trail:", len(history.get("audit_trail", [])))
for a in history.get("audit_trail", []):
    print(f"  {a['actor']}: {a['action']}")

print("\n=== 13. DASHBOARDS ===")
eng_dash = api("GET", "/api/dashboard/engineer", token=token)
print("Engineer dashboard stats:", eng_dash.get("stats"))
off_dash = api("GET", "/api/dashboard/officer", token=officer_token)
print("Officer dashboard stats:", off_dash.get("stats"))

print("\n=== ALL TESTS COMPLETED ===")
