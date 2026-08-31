from typing import cast

from fastapi import Request

from app.health import ReadinessService
from app.storage.resources import AppResources


def get_resources(request: Request) -> AppResources:
    return cast(AppResources, request.app.state.resources)


def get_readiness_service(request: Request) -> ReadinessService:
    return get_resources(request).readiness
