import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.agent.models import AgentRun
from app.events.models import AgentEvent
from app.events.repository import EventRepository

TERMINAL_EVENT_TYPES = frozenset({"run_completed", "run_failed", "run_cancelled"})


class EventBus:
    def __init__(self, repository: EventRepository) -> None:
        self._repository = repository
        self._conditions: dict[str, asyncio.Condition] = {}

    async def emit(
        self,
        run: AgentRun,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> AgentEvent:
        event = AgentEvent(
            run_id=run.id,
            sequence=len(run.trace) + 1,
            type=event_type,
            payload=payload or {},
        )
        await self._repository.append(event)
        run.trace.append(event)
        condition = self._conditions.setdefault(run.id, asyncio.Condition())
        async with condition:
            condition.notify_all()
        return event.model_copy(deep=True)

    async def list_after(self, run_id: str, sequence: int) -> list[AgentEvent]:
        return await self._repository.list_after(run_id, sequence)

    async def stream(
        self,
        run_id: str,
        sequence: int = 0,
    ) -> AsyncIterator[AgentEvent]:
        cursor = sequence
        condition = self._conditions.setdefault(run_id, asyncio.Condition())
        while True:
            events = await self.list_after(run_id, cursor)
            if events:
                for event in events:
                    cursor = event.sequence
                    yield event
                    if event.type in TERMINAL_EVENT_TYPES:
                        return
                continue

            async with condition:
                events = await self.list_after(run_id, cursor)
                if not events:
                    try:
                        await asyncio.wait_for(condition.wait(), timeout=20)
                    except TimeoutError:
                        continue
