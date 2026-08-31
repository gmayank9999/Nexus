from typing import Annotated, cast

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.storage.resources import AppResources

router = APIRouter()


@router.websocket("/ws/runs/{run_id}")
async def stream_run(
    websocket: WebSocket,
    run_id: str,
    last_seen_sequence: Annotated[int, Query(ge=0)] = 0,
) -> None:
    resources = cast(AppResources, websocket.app.state.resources)
    run = await resources.run_repository.get(run_id)
    if run is None:
        await websocket.close(code=4404, reason="Agent run not found")
        return

    await websocket.accept()
    try:
        async for event in resources.event_bus.stream(run_id, last_seen_sequence):
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        return
    await websocket.close(code=1000)
