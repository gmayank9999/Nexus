from typing import Literal

from pydantic import BaseModel, Field

from app import __version__


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "nexus-server"
    version: str = __version__


class ComponentHealth(BaseModel):
    status: Literal["up", "down"]
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    components: dict[str, ComponentHealth] = Field(default_factory=dict)
