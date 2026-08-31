from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from app.config.settings import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_run_api_executes_goal_and_exposes_created_task() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/runs",
            json={"goal": "Create a task to learn Flutter architecture"},
        )
        tasks = await client.get("/api/v1/tasks")
        listed_runs = await client.get("/api/v1/runs")

    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "completed"
    assert run["plan"]["steps"][0]["tool"] == "create_task"
    assert run["trace"][-1]["type"] == "run_completed"
    assert tasks.status_code == 200
    assert tasks.json()[0]["title"] == "Learn flutter architecture"
    assert listed_runs.json()[0]["id"] == run["id"]


@pytest.mark.asyncio
async def test_missing_run_returns_structured_404() -> None:
    async with api_client() as client:
        response = await client.get("/api/v1/runs/run_missing")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "RUN_NOT_FOUND"


@asynccontextmanager
async def api_client() -> AsyncIterator[AsyncClient]:
    app = create_app(
        Settings(
            app_env="test",
            nexus_llm_provider="mock",
            database_url="postgresql+asyncpg://nexus:nexus@localhost:5432/nexus",
            redis_url="redis://localhost:6379/15",
        )
    )
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
