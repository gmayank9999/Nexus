"""Memory repository: in-memory (test) and SQL (prod)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.memory.models import Memory, MemoryCategory
from app.storage.memory_tables import memories


class MemoryRepository(ABC):
    @abstractmethod
    async def create(self, memory: Memory) -> None: ...

    @abstractmethod
    async def get(self, memory_id: str) -> Memory | None: ...

    @abstractmethod
    async def list_for_user(
        self,
        user_id: str,
        category: MemoryCategory | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[Memory]: ...

    @abstractmethod
    async def delete(self, memory_id: str) -> None: ...

    @abstractmethod
    async def update_confidence(self, memory_id: str, confidence: float) -> None: ...


class InMemoryMemoryRepository(MemoryRepository):
    def __init__(self) -> None:
        self._store: dict[str, Memory] = {}

    async def create(self, memory: Memory) -> None:
        self._store[memory.id] = memory

    async def get(self, memory_id: str) -> Memory | None:
        return self._store.get(memory_id)

    async def list_for_user(
        self,
        user_id: str,
        category: MemoryCategory | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[Memory]:
        results = [
            m
            for m in self._store.values()
            if m.user_id == user_id
            and m.confidence >= min_confidence
            and (category is None or m.category == category)
        ]
        results.sort(key=lambda m: m.updated_at, reverse=True)
        return results[:limit]

    async def delete(self, memory_id: str) -> None:
        self._store.pop(memory_id, None)

    async def update_confidence(self, memory_id: str, confidence: float) -> None:
        if memory_id in self._store:
            m = self._store[memory_id]
            self._store[memory_id] = m.model_copy(
                update={"confidence": confidence, "updated_at": datetime.now(UTC)}
            )


class SqlMemoryRepository(MemoryRepository):
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def create(self, memory: Memory) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                insert(memories).values(
                    id=memory.id,
                    user_id=memory.user_id,
                    data=memory.model_dump_for_db(),
                    created_at=memory.created_at,
                )
            )

    async def get(self, memory_id: str) -> Memory | None:
        async with self._engine.connect() as conn:
            row = await conn.execute(
                select(memories.c.data).where(memories.c.id == memory_id)
            )
            result = row.first()
            return Memory.model_validate(result[0]) if result else None

    async def list_for_user(
        self,
        user_id: str,
        category: MemoryCategory | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[Memory]:
        async with self._engine.connect() as conn:
            rows = await conn.execute(
                select(memories.c.data)
                .where(memories.c.user_id == user_id)
                .order_by(memories.c.created_at.desc())
                .limit(limit * 2)  # fetch extra, filter in Python
            )
            all_memories = [Memory.model_validate(r[0]) for r in rows]

        return [
            m
            for m in all_memories
            if m.confidence >= min_confidence
            and (category is None or m.category == category)
        ][:limit]

    async def delete(self, memory_id: str) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(delete(memories).where(memories.c.id == memory_id))

    async def update_confidence(self, memory_id: str, confidence: float) -> None:
        m = await self.get(memory_id)
        if m is None:
            return
        updated = m.model_copy(
            update={"confidence": confidence, "updated_at": datetime.now(UTC)}
        )
        async with self._engine.begin() as conn:
            from sqlalchemy import update as sa_update

            await conn.execute(
                sa_update(memories)
                .where(memories.c.id == memory_id)
                .values(data=updated.model_dump_for_db())
            )
