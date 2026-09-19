import asyncio
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.storage.tables import tasks as task_table


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

    async def update_status(
        self, task_id: str, user_id: str, status: TaskStatus
    ) -> TaskRecord | None: ...


class InMemoryTaskRepository:
    """Isolated task store for tests."""

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

    async def update_status(
        self, task_id: str, user_id: str, status: TaskStatus
    ) -> TaskRecord | None:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.user_id != user_id:
                return None
            task.status = status
            return task.model_copy(deep=True)


class SqlTaskRepository:
    def __init__(self, database: AsyncEngine) -> None:
        self._database = database

    async def create(
        self, *, user_id: str, run_id: str, title: str, description: str | None
    ) -> TaskRecord:
        task = TaskRecord(
            id=f"task_{uuid4().hex}",
            user_id=user_id,
            run_id=run_id,
            title=title,
            description=description,
        )
        async with self._database.begin() as connection:
            await connection.execute(insert(task_table).values(**task.model_dump()))
        return task

    async def list_for_user(self, user_id: str) -> list[TaskRecord]:
        query = (
            select(task_table)
            .where(task_table.c.user_id == user_id)
            .order_by(task_table.c.created_at.desc(), task_table.c.id)
        )
        async with self._database.connect() as connection:
            rows = (await connection.execute(query)).mappings().all()
        return [TaskRecord.model_validate(dict(row)) for row in rows]

    async def update_status(
        self, task_id: str, user_id: str, status: TaskStatus
    ) -> TaskRecord | None:
        query = (
            update(task_table)
            .where(task_table.c.id == task_id, task_table.c.user_id == user_id)
            .values(status=status)
            .returning(*task_table.c)
        )
        async with self._database.begin() as connection:
            row = (await connection.execute(query)).mappings().one_or_none()
        return TaskRecord.model_validate(dict(row)) if row is not None else None
