from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.schemas.health import HealthResponse, ReadinessResponse
from app.dependencies import get_readiness_service
from app.health import ReadinessService

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return process liveness without touching external dependencies."""
    return HealthResponse()


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(
    response: Response,
    service: Annotated[ReadinessService, Depends(get_readiness_service)],
) -> ReadinessResponse:
    """Report whether dependencies required to serve requests are reachable."""
    result = await service.check()
    if result.status != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
