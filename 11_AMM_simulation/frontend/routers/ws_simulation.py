"""WebSocket endpoint for live simulation events."""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..dependencies import get_engine

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for conn in dead:
            self.disconnect(conn)


manager = ConnectionManager()


@router.websocket("/live")
async def websocket_live(websocket: WebSocket):
    """Live simulation event stream."""
    await manager.connect(websocket)
    engine = get_engine()

    try:
        # Send initial state
        await websocket.send_json({
            "type": "init",
            "data": engine.get_state_snapshot(),
        })

        last_step = engine.step_number
        while True:
            await asyncio.sleep(0.5)  # Poll every 500ms

            current_step = engine.step_number
            if current_step != last_step:
                # Send updated state
                await websocket.send_json({
                    "type": "state_update",
                    "data": engine.get_state_snapshot(),
                })
                last_step = current_step

            # Check for client messages
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                data = json.loads(msg)

                if data.get("action") == "step":
                    engine.step()
                    await websocket.send_json({
                        "type": "state_update",
                        "data": engine.get_state_snapshot(),
                    })

                elif data.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})

            except asyncio.TimeoutError:
                pass  # No client message, continue polling

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
