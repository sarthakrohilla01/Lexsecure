"""WebSocket Real-Time Event Notification Hub"""

import asyncio
import json
from typing import List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.security.jwt import decode_access_token

router = APIRouter(tags=["WebSockets"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop):
        """Binds the server event loop so sync handlers can schedule broadcasts."""
        self._loop = loop

    def unbind_loop(self):
        self._loop = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event_type: str, data: dict):
        payload = json.dumps({"event": event_type, "data": data})
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception:
                self.disconnect(connection)

    def broadcast_sync(self, event_type: str, data: dict):
        """Thread-safe publish for sync (threadpool) request handlers. Silently no-ops if the loop isn't running or there are no subscribers."""
        loop = self._loop
        if loop is None or loop.is_closed() or not self.active_connections:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.broadcast(event_type, data), loop)
        except RuntimeError:
            pass

ws_manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    payload = decode_access_token(token) if token else None
    if not payload or payload.get("scope") == "mfa_enroll":
        await websocket.close(code=4401)
        return
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
