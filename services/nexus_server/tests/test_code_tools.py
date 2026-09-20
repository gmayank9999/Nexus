from unittest.mock import AsyncMock

import pytest

from app.agent.executor import Executor
from app.agent.planner import Planner
from app.agent.repository import InMemoryRunRepository
from app.agent.runtime import AgentRuntime
from app.code.repository import InMemoryCodeRepository
from app.events.bus import EventBus
from app.events.repository import InMemoryEventRepository
from app.memory.extractor import MemoryExtractor
from app.providers.mock import MockProvider
from app.tools.base import ToolContext, ToolError
from app.tools.code import (
    FindSymbolTool,
    ListRepositoriesTool,
    ReadFileTool,
    SearchCodeTool,
)
from app.tools.registry import ToolRegistry
from tests.test_code import archive, index
from tests.test_run_api import api_client, wait_for_terminal_run


async def tools_for(files: dict[str, str]):
    repository = InMemoryCodeRepository()
    snapshot = index(files)
    await repository.create(snapshot)
    tools = ToolRegistry()
    for tool in [ListRepositoriesTool, SearchCodeTool, ReadFileTool, FindSymbolTool]:
        tools.register(tool(repository))
    return tools, snapshot.id


def context(user_id: str = "local") -> ToolContext:
    return ToolContext(run_id="run_test", user_id=user_id)


async def test_tools_return_cited_read_only_evidence() -> None:
    tools, repository_id = await tools_for(
        {"app.py": "class App:\n    def login(self):\n        return 1"}
    )
    listed = await tools.execute("list_repositories", {}, context())
    assert listed.output["repositories"][0]["id"] == repository_id
    args = {"repository_id": repository_id, "query": "login"}
    searched = await tools.execute("search_code", args, context())
    assert searched.output["matches"][0]["line"] == 2
    assert len(searched.output["matches"][0]["sha256"]) == 64
    symbols = await tools.execute("find_symbol", args, context())
    assert symbols.output["symbols"][0]["name"] == "App.login"
    read = await tools.execute(
        "read_file",
        {"repository_id": repository_id, "path": "app.py", "start_line": 2},
        context(),
    )
    assert read.output["content"].startswith("    def login")
    assert read.output["start_line"] == 2


@pytest.mark.parametrize(
    "tool,args",
    [
        ("search_code", {"query": "login"}),
        ("find_symbol", {"query": "login"}),
        ("read_file", {"path": "app.py"}),
    ],
)
async def test_other_workspace_and_missing_snapshot_match(
    tool: str, args: dict
) -> None:
    tools, repository_id = await tools_for({"app.py": "def login(): pass"})
    for target, user in [(repository_id, "other"), ("repo_missing", "local")]:
        with pytest.raises(ToolError) as error:
            await tools.execute(tool, {"repository_id": target, **args}, context(user))
        assert error.value.code == "REPOSITORY_NOT_FOUND"
    assert (await tools.execute("list_repositories", {}, context("other"))).output[
        "repositories"
    ] == []


@pytest.mark.parametrize(
    "tool,args",
    [
        ("search_code", {"query": " "}),
        ("find_symbol", {"query": "x" * 101}),
        ("read_file", {"path": "app.py", "start_line": 0}),
        ("search_code", {"query": "login", "user_id": "other"}),
    ],
)
async def test_tools_validate_arguments(tool: str, args: dict) -> None:
    tools, repository_id = await tools_for({"app.py": "pass"})
    with pytest.raises(ToolError) as error:
        await tools.execute(tool, {"repository_id": repository_id, **args}, context())
    assert error.value.code == "TOOL_INVALID_ARGUMENTS"


async def test_file_tool_cannot_read_arbitrary_paths() -> None:
    tools, repository_id = await tools_for({"app.py": "pass"})
    with pytest.raises(ToolError) as error:
        await tools.execute(
            "read_file",
            {"repository_id": repository_id, "path": "../../.env"},
            context(),
        )
    assert error.value.code == "SOURCE_FILE_NOT_FOUND"


async def test_output_budgets_and_incomplete_symbols() -> None:
    tools, repository_id = await tools_for(
        {
            "app.py": "\n".join(f"def login_{i}(): pass" for i in range(30)),
            "app.dart": "void main() {}",
            "long.py": "#" + "x" * 25000,
        }
    )
    for tool, key in [("search_code", "matches"), ("find_symbol", "symbols")]:
        result = await tools.execute(
            tool, {"repository_id": repository_id, "query": "login"}, context()
        )
        assert len(result.output[key]) == 20 and result.output["truncated"]
    symbols = await tools.execute(
        "find_symbol", {"repository_id": repository_id, "query": "nothing"}, context()
    )
    assert symbols.output["incomplete_index"] and not symbols.output["symbols"]
    read = await tools.execute(
        "read_file", {"repository_id": repository_id, "path": "long.py"}, context()
    )
    assert len(read.output["content"]) == 20000 and read.output["truncated"]


async def test_mock_code_mission_cites_uploaded_source() -> None:
    async with api_client() as client:
        uploaded = await client.post(
            "/api/v1/repositories?name=Demo",
            files={
                "file": (
                    "demo.zip",
                    archive({"app.py": "def login(): pass"}),
                    "application/zip",
                ),
            },
        )
        repository_id = uploaded.json()["id"]
        for goal in [
            "List repositories",
            f"Search code in {repository_id} for login",
            f"Find symbol in {repository_id} for login",
        ]:
            response = await client.post("/api/v1/runs", json={"goal": goal})
            run = await wait_for_terminal_run(client, response.json()["id"])
            assert run["status"] == "completed"
            assert repository_id in run["final_response"]
            if goal != "List repositories":
                assert "app.py:1" in run["final_response"]
            assert any(event["type"] == "tool_completed" for event in run["trace"])
        assert (await client.get("/api/v1/tasks")).json() == []


async def test_code_mission_skips_automatic_personal_memory_extraction() -> None:
    tools, repository_id = await tools_for(
        {"app.py": "# private implementation detail"}
    )
    provider = MockProvider()
    extractor = AsyncMock(spec=MemoryExtractor)
    runtime = AgentRuntime(
        Planner(provider, tools),
        Executor(provider, tools),
        tools,
        InMemoryRunRepository(),
        EventBus(InMemoryEventRepository()),
        memory_extractor=extractor,
    )
    try:
        run = await runtime.start(
            f"Search code in {repository_id} for private",
            user_id="local",
            max_iterations=12,
        )
        assert run.status == "completed"
        assert run.context.observations[0].tool == "search_code"
        extractor.extract_and_save.assert_not_called()
    finally:
        await runtime.close()
