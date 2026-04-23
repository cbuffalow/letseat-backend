"""
WebSocket endpoint for real-time session updates.

Clients connect to /ws/{session_id}?token=<jwt>
The server broadcasts events to all members of a session when:
  - A new member joins
  - The host starts the session
  - A member finishes swiping
  - All members finish → results are ready
"""

import json
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException

from app.core.security import decode_token

router = APIRouter(tags=["websocket"])

# session_id -> set of connected WebSockets
active_connections: Dict[str, Set[WebSocket]] = {}


async def broadcast(session_id: str, event: dict) -> None:
    """Send a JSON event to all connected clients in a session."""
    connections = active_connections.get(session_id, set())
    disconnected = set()
    for ws in connections:
        try:
            await ws.send_text(json.dumps(event))
        except Exception:
            disconnected.add(ws)
    active_connections[session_id] -= disconnected


@router.websocket("/ws/{session_id}")
async def session_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
):
    # Authenticate via token query param
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001)
            return
    except HTTPException:
        await websocket.close(code=4001)
        return

    await websocket.accept()

    # Register connection
    if session_id not in active_connections:
        active_connections[session_id] = set()
    active_connections[session_id].add(websocket)

    # Notify others that user joined
    await broadcast(session_id, {
        "event": "member_joined",
        "user_id": user_id,
        "member_count": len(active_connections[session_id]),
    })

    try:
        while True:
            # Keep connection alive; client can send pings
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))

    except WebSocketDisconnect:
        active_connections[session_id].discard(websocket)
        await broadcast(session_id, {
            "event": "member_left",
            "user_id": user_id,
            "member_count": len(active_connections.get(session_id, set())),
        })
