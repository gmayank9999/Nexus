import json
import re
from collections import deque

from pydantic import BaseModel

from app.providers.base import LLMResponse, Message, ToolDefinition
from app.providers.errors import ProviderError


class MockProvider:
    """Deterministic provider used by tests, CI, and local demo mode."""

    def __init__(self, responses: list[LLMResponse] | None = None) -> None:
        self._responses = deque(responses or [])

    @property
    def name(self) -> str:
        return "mock"

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse:
        del tools
        if self._responses:
            return self._responses.popleft()
        if response_schema is None:
            return LLMResponse(content="Mock response completed.", model="mock")

        payload = self._last_payload(messages)
        if response_schema.__name__ == "Plan":
            structured = self._plan(payload)
        elif response_schema.__name__ == "ExecutionDecision":
            structured = self._decision(payload)
        else:
            raise ProviderError(
                "MOCK_SCHEMA_UNSUPPORTED",
                f"MockProvider has no fixture for {response_schema.__name__}.",
                retryable=False,
            )
        validated = response_schema.model_validate(structured)
        return LLMResponse(
            content=json.dumps(structured),
            structured_output=validated.model_dump(mode="json"),
            model="mock",
        )

    @staticmethod
    def _last_payload(messages: list[Message]) -> dict[str, object]:
        if not messages:
            return {}
        try:
            value = json.loads(messages[-1].content)
        except json.JSONDecodeError:
            return {"goal": messages[-1].content}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _plan(payload: dict[str, object]) -> dict[str, object]:
        goal = str(payload.get("goal", "Complete the goal"))
        lowered = goal.lower()
        if "calculat" in lowered or re.search(r"\d\s*[-+*/]\s*\d", lowered):
            tool = "calculator"
            title = "Calculate the result"
        elif "time" in lowered:
            tool = "current_time"
            title = "Check the current time"
        else:
            tool = "create_task"
            title = "Create the requested task"
        return {
            "goal": goal,
            "steps": [
                {
                    "id": "step_1",
                    "title": title,
                    "description": goal,
                    "tool": tool,
                    "requires_approval": False,
                }
            ],
        }

    @staticmethod
    def _decision(payload: dict[str, object]) -> dict[str, object]:
        goal = str(payload.get("goal", "Complete the goal"))
        step = payload.get("step")
        step_data = step if isinstance(step, dict) else {}
        tool = str(step_data.get("tool", "create_task"))
        arguments: dict[str, object]
        if tool == "calculator":
            match = re.search(r"(?:calculate\s*)?([\d\s().+*/%-]+)", goal.lower())
            expression = match.group(1).strip() if match else "0"
            arguments = {"expression": expression}
        elif tool == "current_time":
            arguments = {"timezone": "UTC"}
        else:
            title = re.sub(
                r"^(please\s+)?create\s+(a\s+)?task\s+(to\s+)?",
                "",
                goal,
                flags=re.IGNORECASE,
            ).strip(" .")
            arguments = {
                "title": title[:120].capitalize() or "Complete requested goal",
                "description": goal,
            }
        return {"action": "tool_call", "tool": tool, "arguments": arguments}
