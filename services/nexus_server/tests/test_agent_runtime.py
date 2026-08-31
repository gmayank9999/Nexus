import pytest

from app.agent.executor import Executor
from app.agent.models import AgentRun, AgentStatus
from app.agent.planner import Planner
from app.agent.repository import InMemoryRunRepository
from app.agent.runtime import AgentRuntime
from app.agent.state_machine import AgentStateMachine, StateTransitionError
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
