from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from app.events.models import AgentEvent


class AgentStatus(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    EXECUTING = "executing"
    OBSERVING = "observing"
    REPLANNING = "replanning"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlanStep(BaseModel):
    id: str = Field(pattern=r"^step_[a-zA-Z0-9_-]+$")
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    tool: str = Field(min_length=1, max_length=100)
    requires_approval: bool = False


class Plan(BaseModel):
    goal: str = Field(min_length=1, max_length=4000)
    steps: list[PlanStep] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def unique_step_ids(self) -> Self:
        identifiers = [step.id for step in self.steps]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("plan step identifiers must be unique")
        return self


class ActionKind(StrEnum):
    TOOL_CALL = "tool_call"
    RESPOND = "respond"
    REPLAN = "replan"


class ExecutionDecision(BaseModel):
    action: ActionKind
    tool: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    content: str | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> Self:
        if self.action == ActionKind.TOOL_CALL and not self.tool:
            raise ValueError("tool_call decisions require a tool")
        if self.action == ActionKind.RESPOND and not self.content:
            raise ValueError("respond decisions require content")
        return self


class Observation(BaseModel):
    step_id: str
    tool: str
    output: dict[str, Any]


class AgentContext(BaseModel):
    observations: list[Observation] = Field(default_factory=list)


class RunError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class AgentRun(BaseModel):
    id: str
    user_id: str
    goal: str = Field(min_length=1, max_length=4000)
    status: AgentStatus = AgentStatus.CREATED
    plan: Plan | None = None
    current_step: int = Field(default=0, ge=0)
    context: AgentContext = Field(default_factory=AgentContext)
    iteration: int = Field(default=0, ge=0)
    max_iterations: int = Field(default=12, ge=1, le=100)
    final_response: str | None = None
    error: RunError | None = None
    trace: list[AgentEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def is_terminal(self) -> bool:
        return self.status in {
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.CANCELLED,
        }
