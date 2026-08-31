from collections.abc import Awaitable
from dataclasses import dataclass
from typing import cast

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.agent.executor import Executor
from app.agent.planner import Planner
from app.agent.repository import InMemoryRunRepository
from app.agent.runtime import AgentRuntime
from app.config.settings import Settings
from app.health import ReadinessService
from app.providers.base import LLMProvider
from app.providers.factory import create_provider
from app.storage.task_repository import InMemoryTaskRepository
from app.tools.calculator import CalculatorTool
from app.tools.current_time import CurrentTimeTool
from app.tools.registry import ToolRegistry
from app.tools.tasks import CreateTaskTool, ListTasksTool


@dataclass(slots=True)
class AppResources:
    settings: Settings
    database: AsyncEngine
    redis: Redis
    http_client: httpx.AsyncClient
    provider: LLMProvider
    task_repository: InMemoryTaskRepository
    run_repository: InMemoryRunRepository
    tool_registry: ToolRegistry
    agent_runtime: AgentRuntime
    readiness: ReadinessService

    @classmethod
    def create(cls, settings: Settings) -> "AppResources":
        database = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
        )
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        http_client = httpx.AsyncClient()
        provider = create_provider(settings, http_client)
        task_repository = InMemoryTaskRepository()
        run_repository = InMemoryRunRepository()
        tool_registry = ToolRegistry()
        tool_registry.register(CalculatorTool())
        tool_registry.register(CurrentTimeTool())
        tool_registry.register(CreateTaskTool(task_repository))
        tool_registry.register(ListTasksTool(task_repository))
        agent_runtime = AgentRuntime(
            Planner(provider, tool_registry),
            Executor(provider, tool_registry),
            tool_registry,
            run_repository,
        )

        async def check_database() -> None:
            async with database.connect() as connection:
                await connection.execute(text("SELECT 1"))

        async def check_redis() -> None:
            await cast(Awaitable[bool], redis.ping())

        readiness = ReadinessService({"postgres": check_database, "redis": check_redis})
        return cls(
            settings=settings,
            database=database,
            redis=redis,
            http_client=http_client,
            provider=provider,
            task_repository=task_repository,
            run_repository=run_repository,
            tool_registry=tool_registry,
            agent_runtime=agent_runtime,
            readiness=readiness,
        )

    async def close(self) -> None:
        await self.http_client.aclose()
        await self.redis.aclose()
        await self.database.dispose()
