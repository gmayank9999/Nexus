"""Memory repository: in-memory (test) and SQL (prod)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.memory.models import Memory, MemoryCategory
from app.storage.memory_tables import memories


class MemoryRepository(ABC):
    @abstractmethod
    async def create(self, memory: Memory) -> None: ...

    @abstractmethod
    async def get(self, memory_id: str, user_id: str) -> Memory | None: ...

    @abstractmethod
    async def list_for_user(
        self,
        user_id: str,
        category: MemoryCategory | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[Memory]: ...

    @abstractmethod
    async def delete(self, memory_id: str, user_id: str) -> bool: ...

    @abstractmethod
    async def edit_content(
        self, memory_id: str, user_id: str, content: str
    ) -> Memory | None: ...

    @abstractmethod
    async def update_confidence(
        self, memory_id: str, user_id: str, confidence: float
    ) -> None: ...


class InMemoryMemoryRepository(MemoryRepository):
    def __init__(self) -> None:
        self._store: dict[str, Memory] = {}

    async def create(self, memory: Memory) -> None:
        self._store[memory.id] = memory.model_copy(deep=True)

    async def get(self, memory_id: str, user_id: str) -> Memory | None:
        memory = self._store.get(memory_id)
        return (
            memory.model_copy(deep=True)
            if memory is not None and memory.user_id == user_id
            else None
        )

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
        return [m.model_copy(deep=True) for m in results[:limit]]

    async def delete(self, memory_id: str, user_id: str) -> bool:
        memory = self._store.get(memory_id)
        if memory is None or memory.user_id != user_id:
            return False
        del self._store[memory_id]
        return True

    async def edit_content(
        self, memory_id: str, user_id: str, content: str
    ) -> Memory | None:
        memory = await self.get(memory_id, user_id)
        if memory is None:
            return None
        edited = _edited_memory(memory, content)
        self._store[memory_id] = edited
        return edited.model_copy(deep=True)

    async def update_confidence(
        self, memory_id: str, user_id: str, confidence: float
    ) -> None:
        if memory_id in self._store and self._store[memory_id].user_id == user_id:
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

    async def get(self, memory_id: str, user_id: str) -> Memory | None:
        async with self._engine.connect() as conn:
            row = await conn.execute(
                select(memories.c.data).where(
                    memories.c.id == memory_id, memories.c.user_id == user_id
                )
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
        query = select(memories.c.data).where(
            memories.c.user_id == user_id,
            memories.c.data["confidence"].as_float() >= min_confidence,
        )
        if category is not None:
            query = query.where(memories.c.data["category"].as_string() == category)
        query = query.order_by(
            memories.c.data["updated_at"].as_string().desc(), memories.c.id
        ).limit(limit)
        async with self._engine.connect() as conn:
            rows = await conn.execute(query)
            return [Memory.model_validate(r[0]) for r in rows]

    async def delete(self, memory_id: str, user_id: str) -> bool:
        async with self._engine.begin() as conn:
            result = await conn.execute(
                delete(memories).where(
                    memories.c.id == memory_id, memories.c.user_id == user_id
                )
            )
            return result.rowcount > 0

    async def edit_content(
        self, memory_id: str, user_id: str, content: str
    ) -> Memory | None:
        async with self._engine.begin() as conn:
            row = (
                await conn.execute(
                    select(memories.c.data)
                    .where(memories.c.id == memory_id, memories.c.user_id == user_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            edited = _edited_memory(Memory.model_validate(row), content)
            result = await conn.execute(
                update(memories)
                .where(memories.c.id == memory_id, memories.c.user_id == user_id)
                .values(data=edited.model_dump_for_db())
            )
            return edited if result.rowcount else None

    async def update_confidence(
        self, memory_id: str, user_id: str, confidence: float
    ) -> None:
        m = await self.get(memory_id, user_id)
        if m is None:
            return
        updated = m.model_copy(
            update={"confidence": confidence, "updated_at": datetime.now(UTC)}
        )
        async with self._engine.begin() as conn:
            await conn.execute(
                update(memories)
                .where(memories.c.id == memory_id, memories.c.user_id == user_id)
                .values(data=updated.model_dump_for_db())
            )


def _edited_memory(memory: Memory, content: str) -> Memory:
    normalized = content.strip()
    if not normalized or len(normalized) > 500:
        raise ValueError("Memory content must contain 1 to 500 characters.")
    return memory.model_copy(
        update={
            "content": normalized,
            "source": "user",
            "confidence": 1.0,
            "updated_at": datetime.now(UTC),
        }
    )
