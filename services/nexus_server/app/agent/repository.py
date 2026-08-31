import asyncio
from typing import Protocol

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.agent.models import AgentRun
from app.storage.tables import agent_runs


class RunRepository(Protocol):
    async def save(self, run: AgentRun) -> None: ...

    async def get(self, run_id: str) -> AgentRun | None: ...

    async def list_for_user(self, user_id: str) -> list[AgentRun]: ...


class InMemoryRunRepository:
    """Isolated store used by tests."""

    def __init__(self) -> None:
        self._runs: dict[str, AgentRun] = {}
        self._lock = asyncio.Lock()

    async def save(self, run: AgentRun) -> None:
        async with self._lock:
            self._runs[run.id] = run.model_copy(deep=True)

    async def get(self, run_id: str) -> AgentRun | None:
        async with self._lock:
            run = self._runs.get(run_id)
            return run.model_copy(deep=True) if run is not None else None

    async def list_for_user(self, user_id: str) -> list[AgentRun]:
        async with self._lock:
            runs = [
                run.model_copy(deep=True)
                for run in self._runs.values()
                if run.user_id == user_id
            ]
        return sorted(runs, key=lambda run: run.created_at, reverse=True)


class SqlRunRepository:
    def __init__(self, database: AsyncEngine) -> None:
        self._database = database

    async def save(self, run: AgentRun) -> None:
        values = {
            "user_id": run.user_id,
            "data": run.model_dump(mode="json"),
            "created_at": run.created_at,
        }
        async with self._database.begin() as connection:
            result = await connection.execute(
                update(agent_runs).where(agent_runs.c.id == run.id).values(**values)
            )
            if result.rowcount == 0:
                await connection.execute(insert(agent_runs).values(id=run.id, **values))

    async def get(self, run_id: str) -> AgentRun | None:
        query = select(agent_runs.c.data).where(agent_runs.c.id == run_id)
        async with self._database.connect() as connection:
            value = (await connection.execute(query)).scalar_one_or_none()
        return AgentRun.model_validate(value) if value is not None else None

    async def list_for_user(self, user_id: str) -> list[AgentRun]:
        query = (
            select(agent_runs.c.data)
            .where(agent_runs.c.user_id == user_id)
            .order_by(agent_runs.c.created_at.desc())
        )
        async with self._database.connect() as connection:
            values = (await connection.execute(query)).scalars().all()
        return [AgentRun.model_validate(value) for value in values]
