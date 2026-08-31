from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

from app.tools.base import PermissionLevel, Tool, ToolContext, ToolError


class CurrentTimeInput(BaseModel):
    timezone: str = Field(default="UTC", min_length=1, max_length=100)


class CurrentTimeTool(Tool):
    name = "current_time"
    description = "Return the current time in an IANA timezone."
    permission_level = PermissionLevel.READ_ONLY
    input_schema = CurrentTimeInput

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self,
        arguments: BaseModel,
        context: ToolContext,
    ) -> dict[str, Any]:
        del context
        parsed = CurrentTimeInput.model_validate(arguments)
        try:
            timezone = (
                UTC if parsed.timezone.upper() == "UTC" else ZoneInfo(parsed.timezone)
            )
        except ZoneInfoNotFoundError as error:
            raise ToolError(
                "TIMEZONE_NOT_FOUND",
                "The requested timezone is not available.",
                retryable=True,
            ) from error
        value = self._clock().astimezone(timezone)
        return {"timezone": parsed.timezone, "iso8601": value.isoformat()}
