from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self.all_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, request_id: int = None):
        await websocket.accept()
        self.all_connections.add(websocket)
        if request_id:
            if request_id not in self.active_connections:
                self.active_connections[request_id] = set()
            self.active_connections[request_id].add(websocket)

    def disconnect(self, websocket: WebSocket, request_id: int = None):
        self.all_connections.discard(websocket)
        if request_id and request_id in self.active_connections:
            self.active_connections[request_id].discard(websocket)
            if not self.active_connections[request_id]:
                del self.active_connections[request_id]

    async def send_to_request(self, request_id: int, event: str, data: dict):
        if request_id in self.active_connections:
            message = json.dumps({"event": event, "data": data}, default=str)
            dead = []
            for ws in self.active_connections[request_id]:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.active_connections[request_id].discard(ws)

    async def broadcast(self, event: str, data: dict):
        message = json.dumps({"event": event, "data": data}, default=str)
        dead = []
        for ws in self.all_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.all_connections.discard(ws)


manager = ConnectionManager()
