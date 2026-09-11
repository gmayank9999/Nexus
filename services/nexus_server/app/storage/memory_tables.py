"""SQLAlchemy table for memories."""

from sqlalchemy import Column, DateTime, Index, MetaData, String, Table
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine

memory_metadata = MetaData()

memories = Table(
    "memories",
    memory_metadata,
    Column("id", String(80), primary_key=True),
    Column("user_id", String(100), nullable=False),
    Column("data", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("ix_memories_user", memories.c.user_id, memories.c.created_at)


async def initialize_memory_schema(database: AsyncEngine) -> None:
    async with database.begin() as connection:
        await connection.run_sync(memory_metadata.create_all)
