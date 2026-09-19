import json
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.agent.executor import Executor
from app.agent.models import AgentContext, AgentRun, AgentStatus, Observation
from app.agent.planner import Planner
from app.agent.repository import InMemoryRunRepository, RunRepository, SqlRunRepository
from app.agent.runtime import AgentRuntime, RunActionError
from app.events.bus import EventBus
from app.events.repository import InMemoryEventRepository
from app.providers.mock import MockProvider
from app.storage.tables import initialize_schema
from app.storage.task_repository import InMemoryTaskRepository
from app.tools.registry import ToolRegistry
from app.tools.tasks import CreateTaskTool
from tests.test_run_api import api_client, wait_for_terminal_run


def runtime_for(
    runs: RunRepository, provider: MockProvider | None = None
) -> AgentRuntime:
    provider = provider or MockProvider()
    tools = ToolRegistry()
    tools.register(CreateTaskTool(InMemoryTaskRepository()))
    return AgentRuntime(
        Planner(provider, tools),
        Executor(provider, tools),
        tools,
        runs,
        EventBus(InMemoryEventRepository()),
    )


def completed(run_id: str = "run_parent") -> AgentRun:
    return AgentRun(
        id=run_id,
        user_id="local",
        goal="Study Flutter",
        status=AgentStatus.COMPLETED,
        final_response="Created a study task.",
        context=AgentContext(
            observations=[
                Observation(
                    step_id="step_1", tool="create_task", output={"private": "data"}
                )
            ]
        ),
    )


@pytest.mark.asyncio
async def test_follow_up_snapshots_only_goal_and_reply_without_mutating_parent() -> (
    None
):
    runs = InMemoryRunRepository()
    parent = completed()
    await runs.save(parent)
    child = await runtime_for(runs).create(
        "What was the previous result?",
        user_id="local",
        max_iterations=12,
        parent_run_id=parent.id,
    )
    assert child.parent_run_id == parent.id
    assert child.context.observations == []
    assert child.context.conversation[0].response == parent.final_response
    assert "private" not in child.context.model_dump_json()
    assert child.trace[0].payload["parent_run_id"] == parent.id
    child.context.conversation[0].response = "Changed"
    assert await runs.get(parent.id) == parent
    saved = await runs.get(child.id)
    assert saved is not None
    assert saved.context.conversation[0].response == parent.final_response
    fresh = await runtime_for(runs).create(
        "Unrelated", user_id="local", max_iterations=12
    )
    assert fresh.context.conversation == []


@pytest.mark.asyncio
@pytest.mark.parametrize("owner", ["missing", "other"])
async def test_missing_and_other_workspace_parents_are_indistinguishable(
    owner: str,
) -> None:
    runs = InMemoryRunRepository()
    if owner != "missing":
        parent = completed()
        parent.user_id = owner
        await runs.save(parent)
    with pytest.raises(RunActionError) as error:
        await runtime_for(runs).create(
            "Follow up", user_id="local", max_iterations=12, parent_run_id="run_parent"
        )
    assert error.value.code == "RUN_NOT_FOUND"
    assert await runs.list_for_user("local") == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", [s for s in AgentStatus if s != AgentStatus.COMPLETED]
)
async def test_only_completed_parents_are_accepted(status: AgentStatus) -> None:
    runs = InMemoryRunRepository()
    parent = completed()
    parent.status = status
    await runs.save(parent)
    with pytest.raises(RunActionError) as error:
        await runtime_for(runs).create(
            "Follow up", user_id="local", max_iterations=12, parent_run_id=parent.id
        )
    assert error.value.code == "PARENT_RUN_NOT_COMPLETED"


@pytest.mark.asyncio
async def test_long_chains_keep_three_recent_bounded_turns() -> None:
    runs = InMemoryRunRepository()
    parent = completed("run_0")
    parent.goal = "g" * 4000
    parent.final_response = "😀" * 6000
    runtime = runtime_for(runs)
    ids = []
    for _ in range(6):
        await runs.save(parent)
        ids.append(parent.id)
        child = await runtime.create(
            "Next", user_id="local", max_iterations=12, parent_run_id=parent.id
        )
        assert len(child.context.conversation) <= 3
        assert all(
            len(t.goal) <= 2000 and len(t.response) <= 4000
            for t in child.context.conversation
        )
        assert child.context.conversation_truncated
        child.status = AgentStatus.COMPLETED
        child.final_response = "Next reply"
        parent = child
    assert [t.run_id for t in child.context.conversation] == ids[-3:]


@pytest.mark.asyncio
async def test_context_reaches_planner_executor_and_replanner() -> None:
    payloads = []

    class RecordingProvider(MockProvider):
        async def generate(self, messages, *args, **kwargs):  # type: ignore[no-untyped-def]
            payloads.append(json.loads(messages[-1].content))
            return await super().generate(messages, *args, **kwargs)

    runs = InMemoryRunRepository()
    await runs.save(completed())
    runtime = runtime_for(runs, RecordingProvider())
    run = await runtime.start(
        "What was the previous result?",
        user_id="local",
        max_iterations=12,
        parent_run_id="run_parent",
    )
    assert run.status == AgentStatus.COMPLETED
    assert run.final_response == "Mock follow-up: Created a study task."
    assert run.context.observations == []
    tools = ToolRegistry()
    tools.register(CreateTaskTool(InMemoryTaskRepository()))
    assert run.plan is not None
    await Planner(RecordingProvider(), tools).replan(run.goal, run.context, run.plan)
    assert len(payloads) == 3
    assert all(
        p["conversation"][0]["response"] == "Created a study task." for p in payloads
    )


@pytest.mark.asyncio
async def test_conversation_survives_database_reopen(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'conversation.db'}"
    database = create_async_engine(url)
    try:
        await initialize_schema(database)
        runs = SqlRunRepository(database)
        await runs.save(completed())
        child = await runtime_for(runs).create(
            "Follow up", user_id="local", max_iterations=12, parent_run_id="run_parent"
        )
    finally:
        await database.dispose()
    reopened = create_async_engine(url)
    try:
        assert await SqlRunRepository(reopened).get(child.id) == child
    finally:
        await reopened.dispose()


def test_legacy_run_json_defaults_to_no_conversation() -> None:
    run = AgentRun.model_validate(
        {
            "id": "run_old",
            "user_id": "local",
            "goal": "Old goal",
            "context": {"observations": []},
        }
    )
    assert run.parent_run_id is None
    assert run.context.conversation == []


@pytest.mark.asyncio
async def test_follow_up_api_and_workspace_validation() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/runs", json={"goal": "Create a task to study"}
        )
        parent = await wait_for_terminal_run(client, response.json()["id"])
        body = {"goal": "What was the previous result?", "parent_run_id": parent["id"]}
        response = await client.post("/api/v1/runs", json=body)
        assert response.status_code == 201
        child = await wait_for_terminal_run(client, response.json()["id"])
        assert child["parent_run_id"] == parent["id"]
        assert child["final_response"] == f"Mock follow-up: {parent['final_response']}"
        response = await client.post("/api/v1/runs", json={**body, "user_id": "other"})
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "RUN_NOT_FOUND"
        response = await client.post("/api/v1/runs", json={**body, "parent_run_id": ""})
        assert response.status_code == 422
