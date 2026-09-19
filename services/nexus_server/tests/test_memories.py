from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.memory.models import Memory, MemoryCategory
from app.memory.repository import (
    InMemoryMemoryRepository,
    MemoryRepository,
    SqlMemoryRepository,
)
from app.storage.memory_tables import initialize_memory_schema
from tests.test_run_api import api_client


@pytest.fixture(params=["memory", "sql"])
async def repository(
    request: pytest.FixtureRequest, tmp_path: Path
) -> AsyncIterator[MemoryRepository]:
    if request.param == "memory":
        yield InMemoryMemoryRepository()
        return
    database = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'memories.db'}")
    try:
        await initialize_memory_schema(database)
        yield SqlMemoryRepository(database)
    finally:
        await database.dispose()


def memory(**overrides: object) -> Memory:
    return Memory.model_validate(
        {
            "user_id": "local",
            "category": "user_preference",
            "content": "Prefers short examples",
            "confidence": 0.8,
            "run_id": "run_source",
            **overrides,
        }
    )


async def test_edit_preserves_provenance_and_marks_user_confirmation(
    repository: MemoryRepository,
) -> None:
    original = memory()
    await repository.create(original)
    edited = await repository.edit_content(
        original.id, "local", "  Prefers detailed examples  "
    )
    assert edited is not None
    assert edited.content == "Prefers detailed examples"
    assert edited.source == "user" and edited.confidence == 1
    assert edited.run_id == original.run_id
    assert edited.created_at == original.created_at
    assert edited.updated_at >= original.updated_at
    assert original.content == "Prefers short examples"
    assert await repository.get(original.id, "local") == edited


async def test_other_workspace_cannot_read_edit_or_delete(
    repository: MemoryRepository,
) -> None:
    original = memory(user_id="alice")
    await repository.create(original)
    assert await repository.get(original.id, "bob") is None
    assert await repository.edit_content(original.id, "bob", "Changed") is None
    assert not await repository.delete(original.id, "bob")
    await repository.update_confidence(original.id, "bob", 0.1)
    assert await repository.list_for_user("bob") == []
    assert await repository.get(original.id, "alice") == original
    assert await repository.delete(original.id, "alice")
    assert not await repository.delete(original.id, "alice")


async def test_filtering_precedes_limit_and_edits_sort_first(
    repository: MemoryRepository,
) -> None:
    older = datetime.now(UTC) - timedelta(days=1)
    target = memory(created_at=older, updated_at=older)
    await repository.create(target)
    for _ in range(6):
        await repository.create(memory(category="user_goal", confidence=0.1))
    selected = await repository.list_for_user(
        "local", category=MemoryCategory.USER_PREFERENCE, min_confidence=0.7, limit=1
    )
    assert [m.id for m in selected] == [target.id]
    await repository.edit_content(target.id, "local", "Corrected preference")
    assert (await repository.list_for_user("local", limit=1))[0].id == target.id


async def test_repository_returns_isolated_copies(repository: MemoryRepository) -> None:
    original = memory()
    await repository.create(original)
    original.content = "Unstored mutation"
    saved = await repository.get(original.id, "local")
    assert saved is not None and saved.content == "Prefers short examples"
    saved.content = "Another mutation"
    listed = await repository.list_for_user("local")
    assert listed[0].content == "Prefers short examples"
    listed[0].content = "List mutation"
    assert (await repository.list_for_user("local"))[
        0
    ].content == "Prefers short examples"


async def test_edit_survives_database_reopen(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'reopen.db'}"
    database = create_async_engine(url)
    original = memory()
    try:
        await initialize_memory_schema(database)
        repository = SqlMemoryRepository(database)
        await repository.create(original)
        await repository.edit_content(original.id, "local", "Persisted edit")
    finally:
        await database.dispose()
    reopened = create_async_engine(url)
    try:
        saved = await SqlMemoryRepository(reopened).get(original.id, "local")
        assert saved is not None and saved.content == "Persisted edit"
        assert saved.source == "user"
    finally:
        await reopened.dispose()


async def test_memory_api_defaults_to_mission_workspace_and_preserves_legacy_data() -> (
    None
):
    async with api_client() as client:
        body = {"category": "user_preference", "content": "Original"}
        created = await client.post("/api/v1/memories", json=body)
        assert created.status_code == 201
        memory_id = created.json()["id"]
        legacy = await client.post("/api/v1/memories?user_id=default", json=body)
        listed = await client.get("/api/v1/memories")
        assert [m["id"] for m in listed.json()] == [memory_id]
        legacy_list = await client.get("/api/v1/memories?user_id=default")
        assert legacy_list.json()[0]["id"] == legacy.json()["id"]
        edited = await client.patch(
            f"/api/v1/memories/{memory_id}", json={"content": " Edited "}
        )
        assert edited.status_code == 200
        assert edited.json()["content"] == "Edited"
        for method in ("patch", "delete"):
            kwargs = {"json": {"content": "Wrong owner"}} if method == "patch" else {}
            denied = await client.request(
                method, f"/api/v1/memories/{memory_id}?user_id=other", **kwargs
            )
            assert denied.status_code == 404
        deleted = await client.delete(f"/api/v1/memories/{memory_id}")
        assert deleted.status_code == 204
        assert (await client.get("/api/v1/memories")).json() == []


@pytest.mark.parametrize("content", ["", "  \n ", "x" * 501])
async def test_memory_api_rejects_invalid_edits(content: str) -> None:
    async with api_client() as client:
        response = await client.patch(
            "/api/v1/memories/missing", json={"content": content}
        )
        assert response.status_code == 422


@pytest.mark.parametrize("query", ["min_confidence=2", "limit=0", "user_id="])
async def test_memory_api_validates_filters(query: str) -> None:
    async with api_client() as client:
        assert (await client.get(f"/api/v1/memories?{query}")).status_code == 422
