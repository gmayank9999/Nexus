import asyncio
from typing import Protocol

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.events.models import AgentEvent
from app.storage.tables import agent_events


class EventRepository(Protocol):
    async def append(self, event: AgentEvent) -> None: ...

    async def list_after(self, run_id: str, sequence: int) -> list[AgentEvent]: ...


class InMemoryEventRepository:
    def __init__(self) -> None:
        self._events: dict[str, list[AgentEvent]] = {}
        self._lock = asyncio.Lock()

    async def append(self, event: AgentEvent) -> None:
        async with self._lock:
            events = self._events.setdefault(event.run_id, [])
            if events and event.sequence != events[-1].sequence + 1:
                raise ValueError("Agent event sequence is not contiguous")
            events.append(event.model_copy(deep=True))

    async def list_after(self, run_id: str, sequence: int) -> list[AgentEvent]:
        async with self._lock:
            return [
                event.model_copy(deep=True)
                for event in self._events.get(run_id, [])
                if event.sequence > sequence
            ]


class SqlEventRepository:
    def __init__(self, database: AsyncEngine) -> None:
        self._database = database

    async def append(self, event: AgentEvent) -> None:
        async with self._database.begin() as connection:
            await connection.execute(
                insert(agent_events).values(
                    id=event.id,
                    run_id=event.run_id,
                    sequence=event.sequence,
                    type=event.type,
                    payload=event.payload,
                    created_at=event.timestamp,
                )
            )

    async def list_after(self, run_id: str, sequence: int) -> list[AgentEvent]:
        query = (
            select(agent_events)
            .where(
                agent_events.c.run_id == run_id,
                agent_events.c.sequence > sequence,
            )
            .order_by(agent_events.c.sequence)
        )
        async with self._database.connect() as connection:
            rows = (await connection.execute(query)).mappings().all()
        return [
            AgentEvent(
                id=row.id,
                run_id=row.run_id,
                sequence=row.sequence,
                type=row.type,
                timestamp=row.created_at,
                payload=row.payload,
            )
            for row in rows
        ]
