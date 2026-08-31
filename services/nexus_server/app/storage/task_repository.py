import asyncio
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class TaskRecord(BaseModel):
    id: str
    user_id: str
    run_id: str
    title: str
    description: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskRepository(Protocol):
    async def create(
        self,
        *,
        user_id: str,
        run_id: str,
        title: str,
        description: str | None,
    ) -> TaskRecord: ...

    async def list_for_user(self, user_id: str) -> list[TaskRecord]: ...


class InMemoryTaskRepository:
    """Phase 1 repository; the interface remains stable for SQL persistence."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        *,
        user_id: str,
        run_id: str,
        title: str,
        description: str | None,
    ) -> TaskRecord:
        task = TaskRecord(
            id=f"task_{uuid4().hex}",
            user_id=user_id,
            run_id=run_id,
            title=title,
            description=description,
        )
        async with self._lock:
            self._tasks[task.id] = task
        return task.model_copy(deep=True)

    async def list_for_user(self, user_id: str) -> list[TaskRecord]:
        async with self._lock:
            tasks = [
                task.model_copy(deep=True)
                for task in self._tasks.values()
                if task.user_id == user_id
            ]
        return sorted(tasks, key=lambda task: task.created_at, reverse=True)
