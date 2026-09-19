from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.storage.artifact_repository import (
    Artifact,
    ArtifactType,
    SqlArtifactRepository,
)
from app.storage.tables import initialize_schema
from app.storage.task_repository import SqlTaskRepository, TaskStatus


@pytest.mark.asyncio
async def test_outputs_survive_database_reopen(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'outputs.db'}"
    database = create_async_engine(url)
    try:
        await initialize_schema(database)
        tasks = SqlTaskRepository(database)
        task = await tasks.create(
            user_id="alice",
            run_id="run_1",
            title="Study",
            description="Review concepts",
        )
        assert await tasks.update_status(task.id, "bob", TaskStatus.COMPLETED) is None
        await tasks.update_status(task.id, "alice", TaskStatus.COMPLETED)
        artifact = await SqlArtifactRepository(database).create(
            Artifact(
                user_id="alice",
                run_id="run_1",
                title="Study notes",
                type=ArtifactType.STUDY_GUIDE,
                content="# Concepts\nPractice and review.",
            )
        )
    finally:
        await database.dispose()

    reopened = create_async_engine(url)
    try:
        tasks_after = await SqlTaskRepository(reopened).list_for_user("alice")
        assert tasks_after[0].id == task.id
        assert tasks_after[0].status == TaskStatus.COMPLETED
        artifacts = SqlArtifactRepository(reopened)
        saved = await artifacts.get(artifact.id, "alice")
        assert saved is not None and saved.content == artifact.content
        assert await artifacts.get(artifact.id, "bob") is None
        assert await artifacts.list_for_user("alice", "run_other") == []
        assert len(await artifacts.list_for_user("alice", "run_1")) == 1
    finally:
        await reopened.dispose()
