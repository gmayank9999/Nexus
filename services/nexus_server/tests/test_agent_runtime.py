import asyncio

import pytest

from app.agent.executor import Executor
from app.agent.models import AgentRun, AgentStatus
from app.agent.planner import Planner
from app.agent.repository import InMemoryRunRepository
from app.agent.runtime import AgentRuntime
from app.agent.state_machine import AgentStateMachine, StateTransitionError
from app.events.bus import EventBus
from app.events.repository import InMemoryEventRepository
from app.providers.base import LLMResponse
from app.providers.mock import MockProvider
from app.storage.task_repository import InMemoryTaskRepository
from app.tools.calculator import CalculatorTool
from app.tools.current_time import CurrentTimeTool
from app.tools.registry import ToolRegistry
from app.tools.tasks import CreateTaskTool, ListTasksTool


def build_runtime(
    provider: MockProvider | None = None,
) -> tuple[AgentRuntime, InMemoryTaskRepository]:
    model = provider or MockProvider()
    tasks = InMemoryTaskRepository()
    tools = ToolRegistry()
    tools.register(CalculatorTool())
    tools.register(CurrentTimeTool())
    tools.register(CreateTaskTool(tasks))
    tools.register(ListTasksTool(tasks))
    runtime = AgentRuntime(
        Planner(model, tools),
        Executor(model, tools),
        tools,
        InMemoryRunRepository(),
        EventBus(InMemoryEventRepository()),
    )
    return runtime, tasks


@pytest.mark.asyncio
async def test_goal_plans_executes_tool_and_completes() -> None:
    runtime, tasks = build_runtime()

    run = await runtime.start(
        "Create a task to learn Flutter architecture",
        user_id="user_test",
        max_iterations=12,
    )

    stored_tasks = await tasks.list_for_user("user_test")
    assert run.status == AgentStatus.COMPLETED
    assert run.iteration == 1
    assert run.final_response == "Created task: Learn flutter architecture."
    assert stored_tasks[0].title == "Learn flutter architecture"
    assert [entry.sequence for entry in run.trace] == list(range(1, len(run.trace) + 1))
    assert "tool_completed" in {entry.type for entry in run.trace}


@pytest.mark.asyncio
async def test_approval_step_pauses_before_tool_execution() -> None:
    plan = {
        "goal": "External action",
        "steps": [
            {
                "id": "step_1",
                "title": "Wait",
                "description": "Requires approval",
                "tool": "create_task",
                "requires_approval": True,
            }
        ],
    }
    runtime, tasks = build_runtime(MockProvider([LLMResponse(structured_output=plan)]))

    run = await runtime.start("External action", user_id="user_test", max_iterations=12)

    assert run.status == AgentStatus.WAITING_FOR_APPROVAL
    assert await tasks.list_for_user("user_test") == []
    assert run.trace[-1].type == "approval_required"


@pytest.mark.asyncio
async def test_approved_step_resumes_and_completes() -> None:
    plan = {
        "goal": "External action",
        "steps": [
            {
                "id": "step_1",
                "title": "Create task",
                "description": "Create an approved task",
                "tool": "create_task",
                "requires_approval": True,
            }
        ],
    }
    decision = {
        "action": "tool_call",
        "tool": "create_task",
        "arguments": {"title": "Approved task"},
    }
    runtime, tasks = build_runtime(
        MockProvider(
            [
                LLMResponse(structured_output=plan),
                LLMResponse(structured_output=decision),
            ]
        )
    )

    waiting = await runtime.start(
        "External action",
        user_id="user_test",
        max_iterations=12,
    )
    approved = await runtime.approve(waiting.id)
    completed = await runtime.execute(approved)

    assert completed.status == AgentStatus.COMPLETED
    assert (await tasks.list_for_user("user_test"))[0].title == "Approved task"
    approval = next(
        event for event in completed.trace if event.type == "approval_received"
    )
    assert approval.payload["approved"] is True


@pytest.mark.asyncio
async def test_created_run_can_be_cancelled() -> None:
    runtime, _ = build_runtime()
    run = await runtime.create("Cancel me", user_id="user_test", max_iterations=12)

    cancelled = await runtime.cancel(run.id)

    assert cancelled.status == AgentStatus.CANCELLED
    assert cancelled.trace[-1].type == "run_cancelled"


@pytest.mark.asyncio
async def test_max_iterations_fails_safely() -> None:
    plan = {
        "goal": "Create two tasks",
        "steps": [
            {
                "id": "step_1",
                "title": "First",
                "description": "First task",
                "tool": "create_task",
                "requires_approval": False,
            },
            {
                "id": "step_2",
                "title": "Second",
                "description": "Second task",
                "tool": "create_task",
                "requires_approval": False,
            },
        ],
    }
    decision = {
        "action": "tool_call",
        "tool": "create_task",
        "arguments": {"title": "First"},
    }
    runtime, _ = build_runtime(
        MockProvider(
            [
                LLMResponse(structured_output=plan),
                LLMResponse(structured_output=decision),
            ]
        )
    )

    run = await runtime.start("Create two tasks", user_id="user_test", max_iterations=1)

    assert run.status == AgentStatus.FAILED
    assert run.error is not None
    assert run.error.code == "MAX_ITERATIONS_REACHED"


def test_state_machine_rejects_terminal_transitions() -> None:
    run = AgentRun(
        id="run_test",
        user_id="user_test",
        goal="Test",
        status=AgentStatus.COMPLETED,
    )

    with pytest.raises(StateTransitionError):
        AgentStateMachine().transition(run, AgentStatus.EXECUTING)


@pytest.mark.asyncio
async def test_cancelling_running_mission_stops_before_tool_execution() -> None:
    entered = asyncio.Event()

    class SlowProvider(MockProvider):
        async def generate(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            entered.set()
            await asyncio.Event().wait()

    runtime, tasks = build_runtime(SlowProvider())
    run = await runtime.create("Create a task", user_id="user_test", max_iterations=12)
    execution = asyncio.create_task(runtime.execute(run))
    await asyncio.wait_for(entered.wait(), timeout=1)
    cancelled = await runtime.cancel(run.id)
    assert execution.cancelled()
    assert cancelled.status == AgentStatus.CANCELLED
    assert cancelled.trace[-1].type == "run_cancelled"
    assert await tasks.list_for_user("user_test") == []
    replay = await runtime.execute(run)
    assert replay.status == AgentStatus.CANCELLED


@pytest.mark.asyncio
async def test_duplicate_execution_does_not_repeat_completed_tools() -> None:
    runtime, tasks = build_runtime()
    run = await runtime.create("Create a task", user_id="user_test", max_iterations=12)
    results = await asyncio.gather(runtime.execute(run), runtime.execute(run))
    assert all(result.status == AgentStatus.COMPLETED for result in results)
    assert len(await tasks.list_for_user("user_test")) == 1
