from typing import cast

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from app.storage.resources import AppResources
from app.voice.session import serve_voice

router = APIRouter()


@router.get("/api/v1/voice/status")
async def voice_status(request: Request) -> dict[str, object]:
    settings = cast(AppResources, request.app.state.resources).settings
    return {
        "enabled": settings.nexus_enable_voice,
        "provider": settings.nexus_voice_provider,
        "transcription_mode": "final",
        "max_seconds": settings.nexus_voice_max_seconds,
    }


@router.websocket("/ws/voice")
async def voice_input(websocket: WebSocket) -> None:
    resources = cast(AppResources, websocket.app.state.resources)
    origin = websocket.headers.get("origin")
    if origin and origin not in resources.settings.cors_origins:
        await websocket.close(code=4403, reason="Origin not allowed")
        return
    await websocket.accept()
    try:
        if not resources.settings.nexus_enable_voice:
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "VOICE_DISABLED",
                    "message": "Voice is disabled on this server.",
                }
            )
        else:
            await serve_voice(websocket, resources.voice_service)
        if websocket.client_state.name != "DISCONNECTED":
            await websocket.close(code=1000)
    except WebSocketDisconnect:
        return
