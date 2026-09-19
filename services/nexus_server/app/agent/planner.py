import json

from pydantic import ValidationError

from app.agent.models import AgentContext, Plan
from app.agent.prompt_loader import load_prompt
from app.providers.base import LLMProvider, Message, MessageRole
from app.tools.registry import ToolRegistry


class PlanningError(Exception):
    pass


class Planner:
    def __init__(self, provider: LLMProvider, tools: ToolRegistry) -> None:
        self._provider = provider
        self._tools = tools

    async def create_plan(self, goal: str, context: AgentContext) -> Plan:
        return await self._generate("planner", goal, context, previous_plan=None)

    async def replan(self, goal: str, context: AgentContext, plan: Plan) -> Plan:
        return await self._generate("replanner", goal, context, previous_plan=plan)

    async def _generate(
        self,
        prompt_name: str,
        goal: str,
        context: AgentContext,
        previous_plan: Plan | None,
    ) -> Plan:
        payload = {
            "goal": goal,
            "observations": context.model_dump(mode="json")["observations"],
            "conversation": [turn.model_dump() for turn in context.conversation],
            "conversation_truncated": context.conversation_truncated,
            "previous_plan": (
                previous_plan.model_dump(mode="json") if previous_plan else None
            ),
            "tools": [
                definition.model_dump(mode="json")
                for definition in self._tools.definitions()
            ],
        }
        response = await self._provider.generate(
            [
                Message(role=MessageRole.SYSTEM, content=load_prompt(prompt_name)),
                Message(role=MessageRole.USER, content=json.dumps(payload)),
            ],
            tools=self._tools.definitions(),
            response_schema=Plan,
        )
        if response.structured_output is None:
            raise PlanningError("Provider returned no structured plan.")
        try:
            plan = Plan.model_validate(response.structured_output)
        except ValidationError as error:
            raise PlanningError("Provider returned an invalid plan.") from error
        unknown = [
            step.tool for step in plan.steps if not self._tools.contains(step.tool)
        ]
        if unknown:
            raise PlanningError(
                f"Plan requested unregistered tools: {', '.join(unknown)}"
            )
        return plan
