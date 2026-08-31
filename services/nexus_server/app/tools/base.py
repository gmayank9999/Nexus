from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PermissionLevel(StrEnum):
    READ_ONLY = "read_only"
    WRITE_LOCAL = "write_local"
    EXTERNAL_ACTION = "external_action"
    DANGEROUS = "dangerous"


class ToolContext(BaseModel):
    run_id: str
    user_id: str


class ToolResult(BaseModel):
    tool: str
    output: dict[str, Any]
    duration_ms: float = Field(ge=0)


class ToolError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class Tool(ABC):
    name: str
    description: str
    permission_level: PermissionLevel
    input_schema: type[BaseModel]
    timeout_seconds: float = 10

    @abstractmethod
    async def execute(
        self,
        arguments: BaseModel,
        context: ToolContext,
    ) -> dict[str, Any]: ...
