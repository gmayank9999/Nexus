from typing import cast

from fastapi import Request

from app.health import ReadinessService
from app.storage.resources import AppResources


def get_readiness_service(request: Request) -> ReadinessService:
    resources = cast(AppResources, request.app.state.resources)
    return resources.readiness
