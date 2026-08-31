import asyncio
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
        run_id = response.json()["id"]
        run = await wait_for_terminal_run(client, run_id)
        tasks = await client.get("/api/v1/tasks")
        listed_runs = await client.get("/api/v1/runs")
        events = await client.get(f"/api/v1/runs/{run_id}/events?after=2")

    assert response.status_code == 201
    assert response.json()["status"] == "created"
    assert run["status"] == "completed"
    assert run["plan"]["steps"][0]["tool"] == "create_task"
    assert run["trace"][-1]["type"] == "run_completed"
    assert tasks.status_code == 200
    assert tasks.json()[0]["title"] == "Learn flutter architecture"
    assert listed_runs.json()[0]["id"] == run["id"]
    assert events.status_code == 200
    assert events.json()[0]["sequence"] == 3
    assert events.json()[-1]["type"] == "run_completed"


@pytest.mark.asyncio
async def test_missing_run_returns_structured_404() -> None:
    async with api_client() as client:
        response = await client.get("/api/v1/runs/run_missing")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "RUN_NOT_FOUND"


async def wait_for_terminal_run(client: AsyncClient, run_id: str) -> dict[str, object]:
    for _ in range(100):
        response = await client.get(f"/api/v1/runs/{run_id}")
        run = response.json()
        if run["status"] in {"completed", "failed", "cancelled"}:
            return run
        await asyncio.sleep(0.01)
    raise AssertionError("Agent run did not reach a terminal state")


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
