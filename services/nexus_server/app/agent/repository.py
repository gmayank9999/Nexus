import asyncio
from typing import Protocol

from app.agent.models import AgentRun


class RunRepository(Protocol):
    async def save(self, run: AgentRun) -> None: ...

    async def get(self, run_id: str) -> AgentRun | None: ...

    async def list_for_user(self, user_id: str) -> list[AgentRun]: ...


class InMemoryRunRepository:
    """Phase 1 store behind an interface ready for SQL persistence."""

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
