"""WebSocket live event feed (drives the dashboard Event Feed panel)."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import event_bus

router = APIRouter()


@router.websocket("/ws/events")
async def events(ws: WebSocket) -> None:
    await ws.accept()
    try:
        async for event in event_bus.subscribe():
            await ws.send_json(event)
    except WebSocketDisconnect:
        return
