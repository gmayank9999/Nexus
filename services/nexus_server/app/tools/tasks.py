from typing import Any

from pydantic import BaseModel, Field

from app.storage.task_repository import TaskRepository
from app.tools.base import PermissionLevel, Tool, ToolContext


class CreateTaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)


class EmptyInput(BaseModel):
    pass


class CreateTaskTool(Tool):
    name = "create_task"
    description = "Create a persistent task in the user's NEXUS workspace."
    permission_level = PermissionLevel.WRITE_LOCAL
    input_schema = CreateTaskInput

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        arguments: BaseModel,
        context: ToolContext,
    ) -> dict[str, Any]:
        parsed = CreateTaskInput.model_validate(arguments)
        task = await self._repository.create(
            user_id=context.user_id,
            run_id=context.run_id,
            title=parsed.title,
            description=parsed.description,
        )
        return task.model_dump(mode="json")


class ListTasksTool(Tool):
    name = "list_tasks"
    description = "List tasks in the user's NEXUS workspace."
    permission_level = PermissionLevel.READ_ONLY
    input_schema = EmptyInput

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        arguments: BaseModel,
        context: ToolContext,
    ) -> dict[str, Any]:
        EmptyInput.model_validate(arguments)
        tasks = await self._repository.list_for_user(context.user_id)
        return {"tasks": [task.model_dump(mode="json") for task in tasks]}
