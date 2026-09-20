from typing import Protocol

from sqlalchemy import JSON, Column, DateTime, Integer, String, Table, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.code.models import RepositorySnapshot, RepositorySummary
from app.storage.tables import metadata

code_repositories = Table(
    "code_repositories",
    metadata,
    Column("id", String(80), primary_key=True),
    Column("user_id", String(100), nullable=False, index=True),
    Column("name", String(160), nullable=False),
    Column("file_count", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("data", JSON, nullable=False),
)


class CodeRepository(Protocol):
    async def create(self, snapshot: RepositorySnapshot) -> None: ...
    async def get(
        self, repository_id: str, user_id: str
    ) -> RepositorySnapshot | None: ...
    async def list_for_user(self, user_id: str) -> list[RepositorySummary]: ...


def summarize(snapshot: RepositorySnapshot) -> RepositorySummary:
    return RepositorySummary(
        id=snapshot.id,
        name=snapshot.name,
        file_count=len(snapshot.files),
        created_at=snapshot.created_at,
    )


class InMemoryCodeRepository:
    def __init__(self) -> None:
        self._store: dict[str, RepositorySnapshot] = {}

    async def create(self, snapshot: RepositorySnapshot) -> None:
        self._store[snapshot.id] = snapshot.model_copy(deep=True)

    async def get(self, repository_id: str, user_id: str) -> RepositorySnapshot | None:
        snapshot = self._store.get(repository_id)
        return (
            snapshot.model_copy(deep=True)
            if snapshot and snapshot.user_id == user_id
            else None
        )

    async def list_for_user(self, user_id: str) -> list[RepositorySummary]:
        snapshots = sorted(
            (item for item in self._store.values() if item.user_id == user_id),
            key=lambda item: item.created_at,
            reverse=True,
        )
        return [summarize(item) for item in snapshots[:20]]


class SqlCodeRepository:
    def __init__(self, database: AsyncEngine) -> None:
        self._database = database

    async def create(self, snapshot: RepositorySnapshot) -> None:
        async with self._database.begin() as connection:
            await connection.execute(
                insert(code_repositories).values(
                    **summarize(snapshot).model_dump(),
                    user_id=snapshot.user_id,
                    data=snapshot.model_dump(mode="json"),
                )
            )

    async def get(self, repository_id: str, user_id: str) -> RepositorySnapshot | None:
        async with self._database.connect() as connection:
            data = (
                await connection.execute(
                    select(code_repositories.c.data).where(
                        code_repositories.c.id == repository_id,
                        code_repositories.c.user_id == user_id,
                    )
                )
            ).scalar_one_or_none()
        return RepositorySnapshot.model_validate(data) if data is not None else None

    async def list_for_user(self, user_id: str) -> list[RepositorySummary]:
        table = code_repositories.c
        async with self._database.connect() as connection:
            rows = (
                await connection.execute(
                    select(table.id, table.name, table.file_count, table.created_at)
                    .where(table.user_id == user_id)
                    .order_by(table.created_at.desc())
                    .limit(20)
                )
            ).mappings()
            return [RepositorySummary.model_validate(dict(row)) for row in rows]
