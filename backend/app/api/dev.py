"""Developer / demo-admin endpoints.

These are intentionally small, guarded endpoints for demo & QA operations.
They are only reachable with the shared admin token (DEV_ADMIN_TOKEN) so
regular engineers cannot trigger destructive re-seeds.
"""
import hmac
import os
import threading

from fastapi import APIRouter, Depends, Header, HTTPException, status

router = APIRouter(prefix="/api/dev", tags=["dev"])


def _require_admin(x_admin_token: str = Header(default="")) -> None:
    expected = os.getenv("DEV_ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Dev admin token not configured")
    if not hmac.compare_digest(x_admin_token or "", expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


@router.post("/reseed-demo")
def reseed_demo(_: None = Depends(_require_admin)):
    """Regenerate the demo request corpus (MR-1..MR-4) from scratch.

    Runs in a background thread and returns immediately; poll
    /api/dashboard/engineer until the new requests appear.
    """
    def _run():
        try:
            from scripts.seed_demo_requests import seed_demo_requests
            created = seed_demo_requests(force=True)
            print(f"[reseed-demo] created {created} demo request(s).", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[reseed-demo] failed: {e}", flush=True)

    threading.Thread(target=_run, daemon=True).start()
    return {"message": "Demo reseed started"}
