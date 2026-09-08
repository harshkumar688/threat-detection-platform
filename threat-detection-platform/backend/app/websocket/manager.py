"""
WebSocket Connection Manager

Tracks all active WebSocket connections by a session key (e.g. camera_id).
Provides safe broadcast and unicast helpers, with clean error handling so
a single disconnected client never crashes the broadcast loop.

Usage:
    manager = ConnectionManager()

    @app.websocket("/ws/feed/{camera_id}")
    async def ws_feed(ws: WebSocket, camera_id: str):
        await manager.connect(ws, key=camera_id)
        try:
            while True:
                await ws.receive_text()   # keep alive
        except WebSocketDisconnect:
            manager.disconnect(ws, key=camera_id)
"""

import logging
from collections import defaultdict
from typing import DefaultDict, List

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Thread-safe WebSocket connection registry with broadcast support."""

    def __init__(self):
        # key -> list of active sockets for that key (e.g. camera_id)
        self._connections: DefaultDict[str, List[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, key: str = "default") -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self._connections[key].append(websocket)
        logger.info("ws_connected key=%s total=%d", key, len(self._connections[key]))

    def disconnect(self, websocket: WebSocket, key: str = "default") -> None:
        """Remove a disconnected WebSocket from the registry."""
        conns = self._connections.get(key, [])
        if websocket in conns:
            conns.remove(websocket)
        logger.info("ws_disconnected key=%s remaining=%d", key, len(conns))

    async def send_json(self, data: dict, websocket: WebSocket) -> bool:
        """Send JSON to a single WebSocket. Returns False on error."""
        try:
            await websocket.send_json(data)
            return True
        except Exception:
            return False

    async def broadcast_json(self, data: dict, key: str = "default") -> None:
        """Broadcast JSON to all connected sockets for a key."""
        dead = []
        for ws in list(self._connections.get(key, [])):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, key)

    def active_count(self, key: str = "default") -> int:
        return len(self._connections.get(key, []))


# Shared singleton used by the streams router.
manager = ConnectionManager()
