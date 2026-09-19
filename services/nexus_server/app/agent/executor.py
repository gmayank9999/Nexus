import json

from pydantic import ValidationError

from app.agent.models import AgentContext, ExecutionDecision, PlanStep
from app.agent.prompt_loader import load_prompt
from app.providers.base import LLMProvider, Message, MessageRole
from app.tools.registry import ToolRegistry


class ExecutionError(Exception):
    pass


class Executor:
    def __init__(self, provider: LLMProvider, tools: ToolRegistry) -> None:
        self._provider = provider
        self._tools = tools

    async def decide(
        self,
        goal: str,
        step: PlanStep,
        context: AgentContext,
    ) -> ExecutionDecision:
        payload = {
            "goal": goal,
            "step": step.model_dump(mode="json"),
            "observations": context.model_dump(mode="json")["observations"],
            "conversation": [turn.model_dump() for turn in context.conversation],
            "conversation_truncated": context.conversation_truncated,
            "tools": [
                definition.model_dump(mode="json")
                for definition in self._tools.definitions()
            ],
        }
        response = await self._provider.generate(
            [
                Message(role=MessageRole.SYSTEM, content=load_prompt("executor")),
                Message(role=MessageRole.USER, content=json.dumps(payload)),
            ],
            tools=self._tools.definitions(),
            response_schema=ExecutionDecision,
        )
        if response.structured_output is None:
            raise ExecutionError("Provider returned no structured decision.")
        try:
            decision = ExecutionDecision.model_validate(response.structured_output)
        except ValidationError as error:
            raise ExecutionError("Provider returned an invalid decision.") from error
        if decision.tool is not None and not self._tools.contains(decision.tool):
            raise ExecutionError(
                f"Executor requested an unregistered tool: {decision.tool}"
            )
        return decision
