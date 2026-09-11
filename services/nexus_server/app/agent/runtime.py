import asyncio
from datetime import UTC, datetime
from typing import Any, Awaitable
from uuid import uuid4

from app.agent.executor import ExecutionError, Executor
from app.agent.models import ActionKind, AgentRun, AgentStatus, Observation, RunError
from app.agent.planner import Planner, PlanningError
from app.agent.repository import RunRepository
from app.agent.state_machine import AgentStateMachine, StateTransitionError
from app.events.bus import EventBus
from app.memory.extractor import MemoryExtractor
from app.providers.errors import ProviderError
from app.tools.base import ToolContext, ToolError
from app.tools.registry import ToolRegistry


class IterationLimitError(Exception):
    pass


class RunActionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class AgentRuntime:
    def __init__(
        self,
        planner: Planner,
        executor: Executor,
        tools: ToolRegistry,
        runs: RunRepository,
        events: EventBus,
        state_machine: AgentStateMachine | None = None,
        memory_extractor: MemoryExtractor | None = None,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._tools = tools
        self._runs = runs
        self._events = events
        self._states = state_machine or AgentStateMachine()
        self._memory_extractor = memory_extractor
        self._background_tasks: set[asyncio.Task[Any]] = set()

    def _run_in_background(self, coro: Awaitable[Any]) -> None:
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def create(
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
        await self._emit(run, "run_created", {"goal": goal})
        await self._runs.save(run)
        return run.model_copy(deep=True)

    async def start(
        self,
        goal: str,
        *,
        user_id: str,
        max_iterations: int,
    ) -> AgentRun:
        run = await self.create(
            goal,
            user_id=user_id,
            max_iterations=max_iterations,
        )
        return await self.execute(run)

    async def execute(self, run: AgentRun) -> AgentRun:
        if run.is_terminal() or run.status == AgentStatus.WAITING_FOR_APPROVAL:
            return run.model_copy(deep=True)
        try:
            if run.status == AgentStatus.CREATED:
                await self._emit(run, "run_started")
                await self._transition(run, AgentStatus.PLANNING)
                await self._emit(run, "planning_started")
                await self._runs.save(run)
                run.plan = await self._planner.create_plan(run.goal, run.context)
                await self._emit(
                    run,
                    "plan_created",
                    {"plan": run.plan.model_dump(mode="json")},
                )
                await self._transition(run, AgentStatus.EXECUTING)
                await self._runs.save(run)
            elif run.status == AgentStatus.REPLANNING:
                await self._replan(run)

            while not run.is_terminal():
                if run.iteration >= run.max_iterations:
                    raise IterationLimitError("Maximum agent iterations reached.")
                if run.plan is None or run.current_step >= len(run.plan.steps):
                    await self._complete(run)
                    break

                step = run.plan.steps[run.current_step]
                if step.requires_approval:
                    await self._transition(run, AgentStatus.WAITING_FOR_APPROVAL)
                    await self._emit(
                        run,
                        "approval_required",
                        {"step_id": step.id, "description": step.description},
                    )
                    await self._runs.save(run)
                    break

                await self._emit(
                    run,
                    "agent_iteration_started",
                    {"iteration": run.iteration + 1, "step_id": step.id},
                )
                await self._emit(
                    run,
                    "step_started",
                    {"step": step.model_dump(mode="json")},
                )
                decision = await self._executor.decide(run.goal, step, run.context)

                if decision.action == ActionKind.TOOL_CALL:
                    assert decision.tool is not None
                    await self._emit(
                        run,
                        "tool_requested",
                        {"tool": decision.tool, "arguments": decision.arguments},
                    )
                    await self._emit(
                        run,
                        "tool_started",
                        {"tool": decision.tool},
                    )
                    await self._runs.save(run)
                    try:
                        result = await self._tools.execute(
                            decision.tool,
                            decision.arguments,
                            ToolContext(run_id=run.id, user_id=run.user_id),
                        )
                    except ToolError as error:
                        await self._emit(
                            run,
                            "tool_failed",
                            {
                                "tool": decision.tool,
                                "code": error.code,
                                "retryable": error.retryable,
                            },
                        )
                        raise
                    await self._transition(run, AgentStatus.OBSERVING)
                    run.context.observations.append(
                        Observation(
                            step_id=step.id,
                            tool=result.tool,
                            output=result.output,
                        )
                    )
                    await self._emit(
                        run,
                        "tool_completed",
                        result.model_dump(mode="json"),
                    )
                    run.current_step += 1
                    run.iteration += 1
                    if run.current_step >= len(run.plan.steps):
                        await self._complete(run)
                    else:
                        await self._transition(run, AgentStatus.EXECUTING)
                elif decision.action == ActionKind.RESPOND:
                    run.final_response = decision.content
                    run.iteration += 1
                    await self._complete(run)
                else:
                    await self._transition(run, AgentStatus.REPLANNING)
                    run.iteration += 1
                    await self._replan(run)
                await self._runs.save(run)
        except ProviderError as error:
            await self._fail(run, error.code, str(error), error.retryable)
        except ToolError as error:
            await self._fail(run, error.code, str(error), error.retryable)
        except PlanningError as error:
            await self._fail(run, "PLANNING_FAILED", str(error), False)
        except ExecutionError as error:
            await self._fail(run, "EXECUTION_FAILED", str(error), True)
        except IterationLimitError as error:
            await self._fail(run, "MAX_ITERATIONS_REACHED", str(error), False)
        except StateTransitionError as error:
            await self._fail(run, "INVALID_STATE_TRANSITION", str(error), False)

        await self._runs.save(run)
        return run.model_copy(deep=True)

    async def approve(self, run_id: str) -> AgentRun:
        run = await self._require_waiting_run(run_id)
        step = run.plan.steps[run.current_step] if run.plan is not None else None
        if step is None:
            raise RunActionError("RUN_STEP_MISSING", "The pending step is missing.")
        step.requires_approval = False
        await self._emit(
            run,
            "approval_received",
            {"step_id": step.id, "approved": True},
        )
        await self._transition(run, AgentStatus.EXECUTING)
        await self._runs.save(run)
        return run.model_copy(deep=True)

    async def reject(self, run_id: str) -> AgentRun:
        run = await self._require_waiting_run(run_id)
        step = run.plan.steps[run.current_step] if run.plan is not None else None
        if step is None:
            raise RunActionError("RUN_STEP_MISSING", "The pending step is missing.")
        await self._emit(
            run,
            "approval_received",
            {"step_id": step.id, "approved": False},
        )
        await self._transition(run, AgentStatus.REPLANNING)
        await self._runs.save(run)
        return run.model_copy(deep=True)

    async def cancel(self, run_id: str) -> AgentRun:
        run = await self._runs.get(run_id)
        if run is None:
            raise RunActionError("RUN_NOT_FOUND", "Agent run not found.")
        if run.is_terminal():
            raise RunActionError(
                "RUN_ALREADY_TERMINAL", "Agent run is already terminal."
            )
        await self._transition(run, AgentStatus.CANCELLED)
        await self._emit(run, "run_cancelled")
        await self._runs.save(run)
        return run.model_copy(deep=True)

    async def _require_waiting_run(self, run_id: str) -> AgentRun:
        run = await self._runs.get(run_id)
        if run is None:
            raise RunActionError("RUN_NOT_FOUND", "Agent run not found.")
        if run.status != AgentStatus.WAITING_FOR_APPROVAL:
            raise RunActionError(
                "RUN_NOT_WAITING_FOR_APPROVAL",
                "Agent run is not waiting for approval.",
            )
        return run

    async def _replan(self, run: AgentRun) -> None:
        if run.plan is None:
            raise PlanningError("Cannot replan a run without an existing plan.")
        await self._emit(run, "replanning_started")
        run.plan = await self._planner.replan(run.goal, run.context, run.plan)
        run.current_step = 0
        await self._emit(
            run,
            "plan_created",
            {"plan": run.plan.model_dump(mode="json"), "replanned": True},
        )
        await self._transition(run, AgentStatus.EXECUTING)
        await self._runs.save(run)

    async def _complete(self, run: AgentRun) -> None:
        if run.final_response is None:
            run.final_response = self._completion_message(run)
        await self._emit(run, "agent_message", {"content": run.final_response})
        await self._transition(run, AgentStatus.COMPLETED)
        await self._emit(run, "run_completed", {"response": run.final_response})

        if self._memory_extractor is not None:
            summary = self._build_run_summary(run)
            self._run_in_background(
                self._memory_extractor.extract_and_save(
                    user_id=run.user_id,
                    run_id=run.id,
                    summary=summary,
                )
            )

    def _build_run_summary(self, run: AgentRun) -> str:
        parts = [f"Goal: {run.goal}"]
        if run.plan:
            parts.append(f"Plan: {run.plan.model_dump_json()}")
        for obs in run.context.observations:
            parts.append(f"Tool {obs.tool} output: {obs.output}")
        if run.final_response:
            parts.append(f"Final response: {run.final_response}")
        return "\n".join(parts)

    async def _fail(
        self,
        run: AgentRun,
        code: str,
        message: str,
        retryable: bool,
    ) -> None:
        run.error = RunError(code=code, message=message, retryable=retryable)
        if run.status != AgentStatus.FAILED:
            await self._transition(run, AgentStatus.FAILED)
        await self._emit(run, "run_failed", run.error.model_dump(mode="json"))

    async def _transition(self, run: AgentRun, target: AgentStatus) -> None:
        previous = run.status
        self._states.transition(run, target)
        await self._emit(
            run,
            "status_changed",
            {"from": previous.value, "to": target.value},
        )

    async def _emit(
        self,
        run: AgentRun,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        await self._events.emit(run, event_type, payload)
        run.updated_at = datetime.now(UTC)

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
