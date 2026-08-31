import asyncio

import pytest

from app.agent.models import AgentRun
from app.events.bus import EventBus
from app.events.repository import InMemoryEventRepository


@pytest.mark.asyncio
async def test_event_bus_replays_only_events_after_cursor() -> None:
    bus = EventBus(InMemoryEventRepository())
    run = AgentRun(id="run_test", user_id="user_test", goal="Test events")
    await bus.emit(run, "run_created")
    await bus.emit(run, "run_started")
    await bus.emit(run, "run_completed")

    replay = await bus.list_after(run.id, 1)

    assert [event.sequence for event in replay] == [2, 3]
    assert [event.type for event in replay] == ["run_started", "run_completed"]


@pytest.mark.asyncio
async def test_event_stream_wakes_for_new_event_and_finishes_on_terminal() -> None:
    bus = EventBus(InMemoryEventRepository())
    run = AgentRun(id="run_test", user_id="user_test", goal="Test streaming")

    async def receive() -> list[str]:
        return [event.type async for event in bus.stream(run.id)]

    receiver = asyncio.create_task(receive())
    await asyncio.sleep(0)
    await bus.emit(run, "run_created")
    await bus.emit(run, "run_completed")

    assert await asyncio.wait_for(receiver, timeout=1) == [
        "run_created",
        "run_completed",
    ]
