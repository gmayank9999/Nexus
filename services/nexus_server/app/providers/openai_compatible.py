from typing import Any

import httpx
from pydantic import BaseModel, SecretStr

from app.providers.base import LLMResponse, Message, ToolDefinition
from app.providers.errors import ProviderConfigurationError, ProviderError
from app.providers.http_utils import parse_structured_content


class OpenAICompatibleProvider:
    """Adapter for servers that implement the Chat Completions wire format."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        model: str,
        api_key: SecretStr | None = None,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "openai_compatible"

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse:
        if not self._base_url or not self._model:
            raise ProviderConfigurationError(
                "NEXUS_LLM_BASE_URL and NEXUS_LLM_MODEL must be configured."
            )
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [message.model_dump(mode="json") for message in messages],
        }
        if tools:
            payload["tools"] = [self._tool_payload(tool) for tool in tools]
        if response_schema is not None:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Accept": "application/json"}
        if self._api_key is not None:
            headers["Authorization"] = f"Bearer {self._api_key.get_secret_value()}"

        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise ProviderError(
                "PROVIDER_TIMEOUT", "The model endpoint timed out.", retryable=True
            ) from error
        except httpx.HTTPError as error:
            raise ProviderError(
                "PROVIDER_UNAVAILABLE",
                "The model endpoint is unavailable.",
                retryable=True,
            ) from error

        content = self._extract_content(response.json())
        return LLMResponse(
            content=content,
            structured_output=parse_structured_content(content, response_schema),
            model=self._model,
        )

    @staticmethod
    def _extract_content(data: object) -> str:
        if not isinstance(data, dict):
            raise ProviderError(
                "INVALID_PROVIDER_RESPONSE",
                "The model endpoint returned an invalid response.",
                retryable=True,
            )
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError(
                "INVALID_PROVIDER_RESPONSE",
                "The model endpoint returned no choices.",
                retryable=True,
            )
        first = choices[0]
        if not isinstance(first, dict):
            raise ProviderError(
                "INVALID_PROVIDER_RESPONSE", "Invalid choice.", retryable=True
            )
        message = first.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ProviderError(
                "INVALID_PROVIDER_RESPONSE",
                "Missing assistant content.",
                retryable=True,
            )
        content = message["content"]
        assert isinstance(content, str)
        return content

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
