import asyncio
from collections.abc import Awaitable, Callable

from app.api.schemas.health import ComponentHealth, ReadinessResponse

HealthCheck = Callable[[], Awaitable[None]]


class ReadinessService:
    """Combines independent dependency checks into a stable API response."""

    def __init__(self, checks: dict[str, HealthCheck]) -> None:
        self._checks = checks

    async def check(self) -> ReadinessResponse:
        names = list(self._checks)
        outcomes = await asyncio.gather(
            *(self._checks[name]() for name in names),
            return_exceptions=True,
        )
        components = {
            name: self._component(outcome)
            for name, outcome in zip(names, outcomes, strict=True)
        }
        overall = (
            "ready"
            if all(component.status == "up" for component in components.values())
            else "not_ready"
        )
        return ReadinessResponse(status=overall, components=components)

    @staticmethod
    def _component(outcome: object) -> ComponentHealth:
        if isinstance(outcome, BaseException):
            return ComponentHealth(
                status="down",
                detail=type(outcome).__name__,
            )
        return ComponentHealth(status="up")
