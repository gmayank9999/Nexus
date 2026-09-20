import pytest

from app.memory.models import Memory, MemoryCategory
from app.memory.repository import InMemoryMemoryRepository
from app.tools.base import ToolContext, ToolError
from app.tools.registry import ToolRegistry
from app.tools.search_memories import SearchMemoriesTool
from tests.test_run_api import api_client, wait_for_terminal_run


def memory(content: str, **values: object) -> Memory:
    return Memory.model_validate(
        {
            "user_id": "local",
            "category": "user_preference",
            "content": content,
            "confidence": 0.8,
            **values,
        }
    )


async def search(repository: InMemoryMemoryRepository, **arguments: object) -> dict:
    registry = ToolRegistry()
    registry.register(SearchMemoriesTool(repository))
    result = await registry.execute(
        "search_memories",
        {"query": "Flutter examples", **arguments},
        ToolContext(run_id="run_test", user_id="local"),
    )
    return result.output


async def test_search_ranking_provenance_and_workspace_isolation() -> None:
    repository = InMemoryMemoryRepository()
    relevant = memory("Prefers Flutter examples", source="user", run_id="run_source")
    for item in [
        relevant,
        memory("Flutter only"),
        memory("Unrelated"),
        memory("Flutter examples secret", user_id="other"),
        memory("Flutter examples uncertain", confidence=0.1),
    ]:
        await repository.create(item)
    result = await search(repository)
    assert len(result["memories"]) == 2
    first = result["memories"][0]
    assert first["id"] == relevant.id
    assert first["source"] == "user" and first["run_id"] == "run_source"
    assert first["matched_terms"] == 2
    assert "secret" not in str(result) and "uncertain" not in str(result)


async def test_result_and_content_budgets_are_explicit() -> None:
    repository = InMemoryMemoryRepository()
    for _ in range(110):
        await repository.create(memory("Flutter " + "x" * 1000))
    result = await search(repository)
    assert result["candidates_scanned"] == 100
    assert result["candidate_limit_reached"]
    assert result["more_matches"]
    assert len(result["memories"]) == 5
    assert all(
        len(item["content"]) == 500 and item["content_truncated"]
        for item in result["memories"]
    )


async def test_category_unicode_casefold_and_live_edits() -> None:
    repository = InMemoryMemoryRepository()
    item = memory("CAFÉ examples", category=MemoryCategory.PROJECT_CONTEXT)
    await repository.create(item)
    result = await search(repository, query="café", category="project_context")
    assert result["memories"][0]["id"] == item.id
    assert not (await search(repository, query="café", category="user_goal"))[
        "memories"
    ]
    await repository.edit_content(item.id, "local", "Different preference")
    assert not (await search(repository, query="café"))["memories"]
    assert (await search(repository, query="different"))["memories"][0][
        "source"
    ] == "user"
    await repository.delete(item.id, "local")
    assert not (await search(repository, query="different"))["memories"]


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": "   "},
        {"query": "!!!"},
        {"query": "x" * 201},
        {"limit": 6},
        {"min_confidence": -1},
        {"user_id": "other"},
    ],
)
async def test_search_rejects_invalid_or_workspace_override_arguments(
    arguments: dict,
) -> None:
    with pytest.raises(ToolError) as error:
        await search(InMemoryMemoryRepository(), **arguments)
    assert error.value.code == "TOOL_INVALID_ARGUMENTS"


async def test_mock_mission_retrieves_saved_memory_in_its_trace() -> None:
    async with api_client() as client:
        saved = await client.post(
            "/api/v1/memories",
            json={
                "category": "user_preference",
                "content": "Prefers Flutter examples",
            },
        )
        response = await client.post(
            "/api/v1/runs", json={"goal": "Search memories for Flutter"}
        )
        assert response.status_code == 201
        run = await wait_for_terminal_run(client, response.json()["id"])
        assert run["status"] == "completed"
        assert saved.json()["id"] in run["final_response"]
        assert "Prefers Flutter examples" in run["final_response"]
        tool_events = [e for e in run["trace"] if e["type"] == "tool_completed"]
        assert tool_events[0]["payload"]["tool"] == "search_memories"
        assert (await client.get("/api/v1/tasks")).json() == []
        other = await client.post(
            "/api/v1/runs",
            json={
                "goal": "Search memories for Flutter",
                "user_id": "other",
            },
        )
        empty = await wait_for_terminal_run(client, other.json()["id"])
        assert (
            empty["final_response"]
            == "No matching saved memories in the bounded keyword search."
        )
