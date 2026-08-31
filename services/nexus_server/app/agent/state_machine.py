from typing import ClassVar

from app.agent.models import AgentRun, AgentStatus


class StateTransitionError(Exception):
    pass


class AgentStateMachine:
    _allowed: ClassVar[dict[AgentStatus, frozenset[AgentStatus]]] = {
        AgentStatus.CREATED: frozenset({AgentStatus.PLANNING, AgentStatus.CANCELLED}),
        AgentStatus.PLANNING: frozenset(
            {
                AgentStatus.EXECUTING,
                AgentStatus.WAITING_FOR_APPROVAL,
                AgentStatus.FAILED,
                AgentStatus.CANCELLED,
            }
        ),
        AgentStatus.WAITING_FOR_APPROVAL: frozenset(
            {
                AgentStatus.EXECUTING,
                AgentStatus.REPLANNING,
                AgentStatus.FAILED,
                AgentStatus.CANCELLED,
            }
        ),
        AgentStatus.EXECUTING: frozenset(
            {
                AgentStatus.OBSERVING,
                AgentStatus.REPLANNING,
                AgentStatus.WAITING_FOR_APPROVAL,
                AgentStatus.COMPLETED,
                AgentStatus.FAILED,
                AgentStatus.CANCELLED,
            }
        ),
        AgentStatus.OBSERVING: frozenset(
            {
                AgentStatus.EXECUTING,
                AgentStatus.REPLANNING,
                AgentStatus.COMPLETED,
                AgentStatus.FAILED,
                AgentStatus.CANCELLED,
            }
        ),
        AgentStatus.REPLANNING: frozenset(
            {
                AgentStatus.EXECUTING,
                AgentStatus.WAITING_FOR_APPROVAL,
                AgentStatus.FAILED,
                AgentStatus.CANCELLED,
            }
        ),
        AgentStatus.COMPLETED: frozenset(),
        AgentStatus.FAILED: frozenset(),
        AgentStatus.CANCELLED: frozenset(),
    }

    def transition(self, run: AgentRun, target: AgentStatus) -> None:
        if target not in self._allowed[run.status]:
            raise StateTransitionError(
                f"Invalid agent transition: {run.status.value} -> {target.value}"
            )
        run.status = target
