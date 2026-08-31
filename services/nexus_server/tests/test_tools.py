from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from app.storage.task_repository import InMemoryTaskRepository
from app.tools.base import PermissionLevel, Tool, ToolContext, ToolError
from app.tools.calculator import CalculatorTool
from app.tools.current_time import CurrentTimeTool
from app.tools.registry import ToolRegistry
from app.tools.tasks import CreateTaskTool, ListTasksTool


@pytest.fixture
def context() -> ToolContext:
    return ToolContext(run_id="run_test", user_id="user_test")


@pytest.mark.asyncio
async def test_calculator_evaluates_arithmetic(context: ToolContext) -> None:
    registry = ToolRegistry()
    registry.register(CalculatorTool())

    result = await registry.execute(
        "calculator", {"expression": "(4 + 6) * 3"}, context
    )

    assert result.output["result"] == 30


@pytest.mark.asyncio
async def test_calculator_rejects_code_execution(context: ToolContext) -> None:
    registry = ToolRegistry()
    registry.register(CalculatorTool())

    with pytest.raises(ToolError, match="arithmetic expression") as captured:
        await registry.execute(
            "calculator", {"expression": "__import__('os').system('whoami')"}, context
        )

    assert captured.value.code == "CALCULATOR_INVALID_EXPRESSION"


@pytest.mark.asyncio
async def test_current_time_uses_injected_clock(context: ToolContext) -> None:
    fixed = datetime(2026, 8, 31, 12, 30, tzinfo=UTC)
    registry = ToolRegistry()
    registry.register(CurrentTimeTool(clock=lambda: fixed))

    result = await registry.execute("current_time", {"timezone": "UTC"}, context)

    assert result.output["iso8601"] == "2026-08-31T12:30:00+00:00"


@pytest.mark.asyncio
async def test_task_tools_are_scoped_to_the_user(context: ToolContext) -> None:
    repository = InMemoryTaskRepository()
    registry = ToolRegistry()
    registry.register(CreateTaskTool(repository))
    registry.register(ListTasksTool(repository))

    created = await registry.execute(
        "create_task",
        {"title": "Learn Riverpod", "description": "Read provider docs"},
        context,
    )
    listed = await registry.execute("list_tasks", {}, context)
    other_user = await registry.execute(
        "list_tasks", {}, ToolContext(run_id="other", user_id="other")
    )

    assert created.output["title"] == "Learn Riverpod"
    assert len(listed.output["tasks"]) == 1
    assert other_user.output["tasks"] == []


@pytest.mark.asyncio
async def test_dangerous_tools_remain_disabled(context: ToolContext) -> None:
    class EmptyInput(BaseModel):
        pass

    class DangerousTool(Tool):
        name = "dangerous"
        description = "Never allowed in the MVP."
        permission_level = PermissionLevel.DANGEROUS
        input_schema = EmptyInput

        async def execute(
            self, arguments: BaseModel, context: ToolContext
        ) -> dict[str, object]:
            raise AssertionError("dangerous tool executed")

    registry = ToolRegistry()
    registry.register(DangerousTool())

    with pytest.raises(ToolError) as captured:
        await registry.execute("dangerous", {}, context, approved=True)

    assert captured.value.code == "TOOL_PERMISSION_DENIED"
