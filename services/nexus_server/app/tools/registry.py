import asyncio
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from app.providers.base import ToolDefinition
from app.tools.base import Tool, ToolContext, ToolError, ToolResult
from app.tools.permissions import PermissionPolicy


class ToolRegistry:
    def __init__(self, permission_policy: PermissionPolicy | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._permission_policy = permission_policy or PermissionPolicy()

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def contains(self, name: str) -> bool:
        return name in self._tools

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema.model_json_schema(),
            )
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
        ]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: ToolContext,
        *,
        approved: bool = False,
    ) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError("TOOL_NOT_FOUND", f"Unknown tool: {name}", retryable=False)
        if not self._permission_policy.allows(tool.permission_level, approved=approved):
            raise ToolError(
                "TOOL_PERMISSION_DENIED",
                f"Permission denied for tool: {name}",
                retryable=False,
            )
        try:
            validated = tool.input_schema.model_validate(arguments)
        except ValidationError as error:
            raise ToolError(
                "TOOL_INVALID_ARGUMENTS",
                f"Invalid arguments for tool: {name}",
                retryable=True,
            ) from error

        started = perf_counter()
        try:
            async with asyncio.timeout(tool.timeout_seconds):
                output = await tool.execute(validated, context)
        except TimeoutError as error:
            raise ToolError(
                "TOOL_TIMEOUT", f"Tool timed out: {name}", retryable=True
            ) from error
        return ToolResult(
            tool=name,
            output=output,
            duration_ms=(perf_counter() - started) * 1000,
        )
