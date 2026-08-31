from collections.abc import Awaitable
from dataclasses import dataclass
from typing import cast

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config.settings import Settings
from app.health import ReadinessService


@dataclass(slots=True)
class AppResources:
    database: AsyncEngine
    redis: Redis
    readiness: ReadinessService

    @classmethod
    def create(cls, settings: Settings) -> "AppResources":
        database = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
        )
        redis = Redis.from_url(settings.redis_url, decode_responses=True)

        async def check_database() -> None:
            async with database.connect() as connection:
                await connection.execute(text("SELECT 1"))

        async def check_redis() -> None:
            await cast(Awaitable[bool], redis.ping())

        readiness = ReadinessService({"postgres": check_database, "redis": check_redis})
        return cls(database=database, redis=redis, readiness=readiness)

    async def close(self) -> None:
        await self.redis.aclose()
        await self.database.dispose()
