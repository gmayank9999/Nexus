from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.agent.executor import ExecutionError, Executor
from app.agent.models import (
    ActionKind,
    AgentRun,
    AgentStatus,
    Observation,
    RunError,
    TraceEntry,
)
from app.agent.planner import Planner, PlanningError
from app.agent.repository import RunRepository
from app.agent.state_machine import AgentStateMachine, StateTransitionError
from app.providers.errors import ProviderError
from app.tools.base import ToolContext, ToolError
from app.tools.registry import ToolRegistry


class IterationLimitError(Exception):
    pass


class AgentRuntime:
    def __init__(
        self,
        planner: Planner,
        executor: Executor,
        tools: ToolRegistry,
        runs: RunRepository,
        state_machine: AgentStateMachine | None = None,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._tools = tools
        self._runs = runs
        self._states = state_machine or AgentStateMachine()

    async def start(
        self,
        goal: str,
        *,
        user_id: str,
        max_iterations: int,
    ) -> AgentRun:
        run = AgentRun(
            id=f"run_{uuid4().hex}",
            user_id=user_id,
            goal=goal,
            max_iterations=max_iterations,
        )
        self._trace(run, "run_created", {"goal": goal})
        await self._runs.save(run)
        return await self.execute(run)

    async def execute(self, run: AgentRun) -> AgentRun:
        if run.is_terminal() or run.status == AgentStatus.WAITING_FOR_APPROVAL:
            return run.model_copy(deep=True)
        try:
            if run.status == AgentStatus.CREATED:
                self._transition(run, AgentStatus.PLANNING)
                self._trace(run, "planning_started")
                run.plan = await self._planner.create_plan(run.goal, run.context)
                self._trace(
                    run,
                    "plan_created",
                    {"plan": run.plan.model_dump(mode="json")},
                )
                self._transition(run, AgentStatus.EXECUTING)

            while not run.is_terminal():
                if run.iteration >= run.max_iterations:
                    raise IterationLimitError("Maximum agent iterations reached.")
                if run.plan is None or run.current_step >= len(run.plan.steps):
                    self._complete(run)
                    break

                step = run.plan.steps[run.current_step]
                if step.requires_approval:
                    self._transition(run, AgentStatus.WAITING_FOR_APPROVAL)
                    self._trace(
                        run,
                        "approval_required",
                        {"step_id": step.id, "description": step.description},
                    )
                    break

                self._trace(
                    run,
                    "agent_iteration_started",
                    {"iteration": run.iteration + 1, "step_id": step.id},
                )
                self._trace(run, "step_started", {"step": step.model_dump(mode="json")})
                decision = await self._executor.decide(run.goal, step, run.context)

                if decision.action == ActionKind.TOOL_CALL:
                    assert decision.tool is not None
                    self._trace(
                        run,
                        "tool_requested",
                        {"tool": decision.tool, "arguments": decision.arguments},
                    )
                    result = await self._tools.execute(
                        decision.tool,
                        decision.arguments,
                        ToolContext(run_id=run.id, user_id=run.user_id),
                    )
                    self._transition(run, AgentStatus.OBSERVING)
                    run.context.observations.append(
                        Observation(
                            step_id=step.id,
                            tool=result.tool,
                            output=result.output,
                        )
                    )
                    self._trace(
                        run,
                        "tool_completed",
                        result.model_dump(mode="json"),
                    )
                    run.current_step += 1
                    run.iteration += 1
                    if run.current_step >= len(run.plan.steps):
                        self._complete(run)
                    else:
                        self._transition(run, AgentStatus.EXECUTING)
                elif decision.action == ActionKind.RESPOND:
                    run.final_response = decision.content
                    run.iteration += 1
                    self._complete(run)
                else:
                    self._transition(run, AgentStatus.REPLANNING)
                    self._trace(run, "replanning_started")
                    run.plan = await self._planner.replan(
                        run.goal, run.context, run.plan
                    )
                    run.current_step = 0
                    run.iteration += 1
                    self._trace(
                        run,
                        "plan_created",
                        {"plan": run.plan.model_dump(mode="json"), "replanned": True},
                    )
                    self._transition(run, AgentStatus.EXECUTING)
                await self._runs.save(run)
        except ProviderError as error:
            self._fail(run, error.code, str(error), error.retryable)
        except ToolError as error:
            self._fail(run, error.code, str(error), error.retryable)
        except PlanningError as error:
            self._fail(run, "PLANNING_FAILED", str(error), False)
        except ExecutionError as error:
            self._fail(run, "EXECUTION_FAILED", str(error), True)
        except IterationLimitError as error:
            self._fail(run, "MAX_ITERATIONS_REACHED", str(error), False)
        except StateTransitionError as error:
            self._fail(run, "INVALID_STATE_TRANSITION", str(error), False)

        await self._runs.save(run)
        return run.model_copy(deep=True)

    def _complete(self, run: AgentRun) -> None:
        if run.final_response is None:
            run.final_response = self._completion_message(run)
        self._transition(run, AgentStatus.COMPLETED)
        self._trace(run, "run_completed", {"response": run.final_response})

    def _fail(self, run: AgentRun, code: str, message: str, retryable: bool) -> None:
        run.error = RunError(code=code, message=message, retryable=retryable)
        if run.status != AgentStatus.FAILED:
            self._transition(run, AgentStatus.FAILED)
        self._trace(run, "run_failed", run.error.model_dump(mode="json"))

    def _transition(self, run: AgentRun, target: AgentStatus) -> None:
        previous = run.status
        self._states.transition(run, target)
        self._trace(
            run,
            "status_changed",
            {"from": previous.value, "to": target.value},
        )

    @staticmethod
    def _completion_message(run: AgentRun) -> str:
        if not run.context.observations:
            return "Goal completed."
        last = run.context.observations[-1]
        if last.tool == "create_task":
            return f"Created task: {last.output.get('title', 'Untitled task')}."
        if last.tool == "calculator":
            return f"Calculated result: {last.output.get('result')}."
        if last.tool == "current_time":
            return f"Current time: {last.output.get('iso8601')}."
        return f"Completed {len(run.context.observations)} tool step(s)."

    @staticmethod
    def _trace(
        run: AgentRun,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        run.trace.append(
            TraceEntry(
                sequence=len(run.trace) + 1,
                type=event_type,
                payload=payload or {},
            )
        )
        run.updated_at = datetime.now(UTC)
