from typing import Any

import httpx
from pydantic import BaseModel

from app.providers.base import LLMResponse, Message, ToolDefinition
from app.providers.errors import ProviderConfigurationError, ProviderError
from app.providers.http_utils import parse_structured_content


class OllamaProvider:
    def __init__(self, client: httpx.AsyncClient, base_url: str, model: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._model = model

    @property
    def name(self) -> str:
        return "ollama"

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse:
        if not self._model:
            raise ProviderConfigurationError(
                "NEXUS_OLLAMA_MODEL must be configured before running an agent."
            )
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [message.model_dump(mode="json") for message in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = [self._tool_payload(tool) for tool in tools]
        if response_schema is not None:
            payload["format"] = response_schema.model_json_schema()

        try:
            response = await self._client.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise ProviderError(
                "PROVIDER_TIMEOUT", "Ollama timed out.", retryable=True
            ) from error
        except httpx.HTTPError as error:
            raise ProviderError(
                "PROVIDER_UNAVAILABLE", "Ollama is unavailable.", retryable=True
            ) from error

        data = response.json()
        if not isinstance(data, dict):
            raise ProviderError(
                "INVALID_PROVIDER_RESPONSE",
                "Ollama returned an invalid response.",
                retryable=True,
            )
        message = data.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ProviderError(
                "INVALID_PROVIDER_RESPONSE",
                "Ollama returned no assistant content.",
                retryable=True,
            )
        content = message["content"]
        assert isinstance(content, str)
        return LLMResponse(
            content=content,
            structured_output=parse_structured_content(content, response_schema),
            model=self._model,
        )

    @staticmethod
    def _tool_payload(tool: ToolDefinition) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }
