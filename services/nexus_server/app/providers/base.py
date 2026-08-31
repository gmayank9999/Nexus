from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    role: MessageRole
    content: str


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class LLMUsage(BaseModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class LLMResponse(BaseModel):
    content: str = ""
    structured_output: dict[str, Any] | None = None
    usage: LLMUsage = Field(default_factory=LLMUsage)
    model: str | None = None


class LLMProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse: ...
