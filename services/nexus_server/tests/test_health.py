from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.router import api_router
from app.api.schemas.health import ReadinessResponse
from app.dependencies import get_readiness_service


class StubReadinessService:
    def __init__(self, status: str) -> None:
        self.status = status

    async def check(self) -> ReadinessResponse:
        component_status = "up" if self.status == "ready" else "down"
        return ReadinessResponse(
            status=self.status,  # type: ignore[arg-type]
            components={"postgres": {"status": component_status}},  # type: ignore[dict-item]
        )


@pytest.mark.asyncio
async def test_health_reports_service_metadata() -> None:
    async with _client(StubReadinessService("ready")) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "nexus-server",
        "version": "0.1.0",
    }


@pytest.mark.asyncio
async def test_ready_returns_200_when_dependencies_are_available() -> None:
    async with _client(StubReadinessService("ready")) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_ready_returns_503_when_a_dependency_is_unavailable() -> None:
    async with _client(StubReadinessService("not_ready")) as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def _test_app(readiness: StubReadinessService) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(api_router)
    app.dependency_overrides[get_readiness_service] = lambda: readiness
    return app


@asynccontextmanager
async def _client(readiness: StubReadinessService) -> AsyncIterator[AsyncClient]:
    app = _test_app(readiness)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
