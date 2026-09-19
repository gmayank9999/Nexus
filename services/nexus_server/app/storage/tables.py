from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.asyncio import AsyncEngine

metadata = MetaData()

agent_runs = Table(
    "agent_runs",
    metadata,
    Column("id", String(80), primary_key=True),
    Column("user_id", String(100), nullable=False),
    Column("data", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("ix_agent_runs_user_created", agent_runs.c.user_id, agent_runs.c.created_at)

agent_events = Table(
    "agent_events",
    metadata,
    Column("id", String(80), primary_key=True),
    Column("run_id", String(80), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("type", String(100), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("run_id", "sequence", name="uq_agent_events_run_sequence"),
)
Index("ix_agent_events_run_sequence", agent_events.c.run_id, agent_events.c.sequence)

tasks = Table(
    "tasks",
    metadata,
    Column("id", String(80), primary_key=True),
    Column("user_id", String(100), nullable=False),
    Column("run_id", String(80), nullable=False),
    Column("title", String(160), nullable=False),
    Column("description", Text),
    Column("status", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("ix_tasks_user_run", tasks.c.user_id, tasks.c.run_id)

artifacts = Table(
    "artifacts",
    metadata,
    Column("id", String(80), primary_key=True),
    Column("user_id", String(100), nullable=False),
    Column("run_id", String(80), nullable=False),
    Column("type", String(40), nullable=False),
    Column("title", String(160), nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("ix_artifacts_user_run", artifacts.c.user_id, artifacts.c.run_id)


async def initialize_schema(database: AsyncEngine) -> None:
    async with database.begin() as connection:
        await connection.run_sync(metadata.create_all)
