import asyncio

import pytest

from app.storage.artifact_repository import (
    Artifact,
    ArtifactType,
    InMemoryArtifactRepository,
)
from app.storage.task_repository import InMemoryTaskRepository, TaskStatus
from tests.test_run_api import api_client


@pytest.mark.asyncio
async def test_task_update_is_user_scoped_and_idempotent() -> None:
    repo = InMemoryTaskRepository()
    task = await repo.create(
        user_id="alice", run_id="r1", title="Review", description=None
    )
    assert await repo.update_status(task.id, "bob", TaskStatus.COMPLETED) is None
    for _ in range(2):
        result = await repo.update_status(task.id, "alice", TaskStatus.COMPLETED)
        assert result is not None and result.status == TaskStatus.COMPLETED
    result = await repo.update_status(task.id, "alice", TaskStatus.PENDING)
    assert result is not None and result.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_artifacts_filter_owner_and_run() -> None:
    repo = InMemoryArtifactRepository()
    artifact = await repo.create(
        Artifact(
            user_id="alice",
            run_id="r1",
            type=ArtifactType.NOTE,
            title="Note",
            content="Study notes",
        )
    )
    assert await repo.get(artifact.id, "bob") is None
    assert await repo.list_for_user("alice", "r2") == []
    assert (await repo.list_for_user("alice", "r1"))[0].content == "Study notes"


@pytest.mark.asyncio
async def test_multistep_mission_creates_task_and_saved_artifact() -> None:
    async with api_client() as client:
        created = await client.post(
            "/api/v1/runs",
            json={
                "goal": "Create a Flutter architecture study guide",
            },
        )
        assert created.status_code == 201
        run_id = created.json()["id"]
        for _ in range(100):
            run = (await client.get(f"/api/v1/runs/{run_id}")).json()
            if run["status"] in {"completed", "failed"}:
                break
            await asyncio.sleep(0.01)
        assert run["status"] == "completed"
        assert run["current_step"] == 2
        tasks = (await client.get("/api/v1/tasks", params={"run_id": run_id})).json()
        assert len(tasks) == 1
        task_id = tasks[0]["id"]
        assert (
            await client.patch(
                f"/api/v1/tasks/{task_id}",
                json={
                    "status": "completed",
                },
            )
        ).json()["status"] == "completed"
        assert (
            await client.patch(
                f"/api/v1/tasks/{task_id}",
                json={
                    "status": "invalid",
                },
            )
        ).status_code == 422
        assert (
            await client.patch(
                f"/api/v1/tasks/{task_id}?user_id=other",
                json={
                    "status": "completed",
                },
            )
        ).status_code == 404
        artifacts = (
            await client.get("/api/v1/artifacts", params={"run_id": run_id})
        ).json()
        assert len(artifacts) == 1 and artifacts[0]["type"] == "study_guide"
        artifact_id = artifacts[0]["id"]
        assert (await client.get(f"/api/v1/artifacts/{artifact_id}")).status_code == 200
        assert (
            await client.get(f"/api/v1/artifacts/{artifact_id}?user_id=other")
        ).status_code == 404
        assert "artifact_created" in {event["type"] for event in run["trace"]}
