import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv

    _here = os.path.dirname(os.path.abspath(__file__))
    for _candidate in (os.path.join(_here, ".env"), os.path.join(_here, "..", ".env")):
        if os.path.exists(_candidate):
            load_dotenv(_candidate)
            break
except Exception:
    pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import FRONTEND_URL, DEMO_MODE
from app.database.connection import init_db
from app.api import auth, requests, officer, dashboard, execution, live
from app.websocket.handler import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from scripts.seed_database import seed_all
    seed_all()
    yield


app = FastAPI(
    title="RailSync AI",
    description="AI-Powered Automatic Railway Maintenance Block Planning System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(requests.router)
app.include_router(officer.router)
app.include_router(dashboard.router)
app.include_router(execution.router)
app.include_router(live.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "demo_mode": DEMO_MODE, "version": "1.0.0"}


@app.websocket("/ws/{request_id}")
async def websocket_endpoint(websocket: WebSocket, request_id: int):
    await manager.connect(websocket, request_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, request_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
