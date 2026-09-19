from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.storage.tables import artifacts


class ArtifactType(StrEnum):
    PLAN = "plan"
    CHECKLIST = "checklist"
    NOTE = "note"
    REPORT = "report"
    STUDY_GUIDE = "study_guide"
    ARCHITECTURE_DIAGRAM = "architecture_diagram"
    CODE_EXPLANATION = "code_explanation"


class ArtifactInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: ArtifactType
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=50000)


class Artifact(ArtifactInput):
    id: str = Field(default_factory=lambda: f"artifact_{uuid4().hex}")
    user_id: str
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ArtifactRepository(Protocol):
    async def create(self, artifact: Artifact) -> Artifact: ...

    async def list_for_user(
        self, user_id: str, run_id: str | None = None
    ) -> list[Artifact]: ...

    async def get(self, artifact_id: str, user_id: str) -> Artifact | None: ...


class InMemoryArtifactRepository:
    def __init__(self) -> None:
        self._artifacts: dict[str, Artifact] = {}

    async def create(self, artifact: Artifact) -> Artifact:
        self._artifacts[artifact.id] = artifact.model_copy(deep=True)
        return artifact.model_copy(deep=True)

    async def list_for_user(
        self, user_id: str, run_id: str | None = None
    ) -> list[Artifact]:
        return sorted(
            [
                a.model_copy(deep=True)
                for a in self._artifacts.values()
                if a.user_id == user_id and (run_id is None or a.run_id == run_id)
            ],
            key=lambda a: a.created_at,
            reverse=True,
        )

    async def get(self, artifact_id: str, user_id: str) -> Artifact | None:
        artifact = self._artifacts.get(artifact_id)
        if artifact is None or artifact.user_id != user_id:
            return None
        return artifact.model_copy(deep=True)


class SqlArtifactRepository:
    def __init__(self, database: AsyncEngine) -> None:
        self._database = database

    async def create(self, artifact: Artifact) -> Artifact:
        async with self._database.begin() as connection:
            await connection.execute(insert(artifacts).values(**artifact.model_dump()))
        return artifact.model_copy(deep=True)

    async def list_for_user(
        self, user_id: str, run_id: str | None = None
    ) -> list[Artifact]:
        query = select(artifacts).where(artifacts.c.user_id == user_id)
        if run_id is not None:
            query = query.where(artifacts.c.run_id == run_id)
        async with self._database.connect() as connection:
            rows = (
                (
                    await connection.execute(
                        query.order_by(artifacts.c.created_at.desc(), artifacts.c.id)
                    )
                )
                .mappings()
                .all()
            )
        return [Artifact.model_validate(dict(row)) for row in rows]

    async def get(self, artifact_id: str, user_id: str) -> Artifact | None:
        async with self._database.connect() as connection:
            row = (
                (
                    await connection.execute(
                        select(artifacts).where(
                            artifacts.c.id == artifact_id,
                            artifacts.c.user_id == user_id,
                        )
                    )
                )
                .mappings()
                .one_or_none()
            )
        return Artifact.model_validate(dict(row)) if row is not None else None
