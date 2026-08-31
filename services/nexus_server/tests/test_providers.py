import json

import httpx
import pytest
from pydantic import BaseModel

from app.providers.base import Message, MessageRole
from app.providers.errors import ProviderConfigurationError
from app.providers.mock import MockProvider
from app.providers.ollama import OllamaProvider


class ExampleOutput(BaseModel):
    answer: str


@pytest.mark.asyncio
async def test_ollama_returns_validated_structured_output() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "local-model"
        assert body["format"]["title"] == "ExampleOutput"
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": '{"answer":"ok"}'}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaProvider(client, "http://ollama.test", "local-model")
        response = await provider.generate(
            [Message(role=MessageRole.USER, content="test")],
            response_schema=ExampleOutput,
        )

    assert response.structured_output == {"answer": "ok"}


@pytest.mark.asyncio
async def test_ollama_requires_an_explicit_model() -> None:
    async with httpx.AsyncClient() as client:
        provider = OllamaProvider(client, "http://ollama.test", "")
        with pytest.raises(ProviderConfigurationError):
            await provider.generate([Message(role=MessageRole.USER, content="test")])


@pytest.mark.asyncio
async def test_mock_provider_is_deterministic_for_unknown_goals() -> None:
    class Plan(BaseModel):
        goal: str
        steps: list[dict[str, object]]

    provider = MockProvider()
    response = await provider.generate(
        [
            Message(
                role=MessageRole.USER,
                content=json.dumps({"goal": "Create a task to learn Riverpod"}),
            )
        ],
        response_schema=Plan,
    )

    assert response.structured_output is not None
    assert response.structured_output["steps"][0]["tool"] == "create_task"
