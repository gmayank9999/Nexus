from fastapi import Request

from app.health import ReadinessService


def get_readiness_service(request: Request) -> ReadinessService:
    return request.app.state.resources.readiness
