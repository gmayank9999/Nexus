import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import cast

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.agent.executor import Executor
from app.agent.models import AgentRun
from app.agent.planner import Planner
from app.agent.repository import InMemoryRunRepository, RunRepository, SqlRunRepository
from app.agent.runtime import AgentRuntime
from app.code.repository import (
    CodeRepository,
    InMemoryCodeRepository,
    SqlCodeRepository,
)
from app.config.settings import Settings
from app.documents.embeddings import LocalEmbeddingProvider
from app.documents.indexer import DocumentIndexer
from app.documents.models import Document
from app.documents.repository import (
    DocumentRepository,
    InMemoryDocumentRepository,
    SqlDocumentRepository,
)
from app.events.bus import EventBus
from app.events.repository import (
    EventRepository,
    InMemoryEventRepository,
    SqlEventRepository,
)
from app.health import ReadinessService
from app.memory.extractor import MemoryExtractor
from app.memory.repository import (
    InMemoryMemoryRepository,
    MemoryRepository,
    SqlMemoryRepository,
)
from app.providers.base import LLMProvider
from app.providers.factory import create_provider
from app.storage.artifact_repository import (
    ArtifactRepository,
    InMemoryArtifactRepository,
    SqlArtifactRepository,
)
from app.storage.doc_tables import initialize_doc_schema
from app.storage.memory_tables import initialize_memory_schema
from app.storage.tables import initialize_schema
from app.storage.task_repository import (
    InMemoryTaskRepository,
    SqlTaskRepository,
    TaskRepository,
)
from app.tools.calculator import CalculatorTool
from app.tools.code import (
    CallSitesTool,
    DependencyGraphTool,
    FindSymbolTool,
    ListRepositoriesTool,
    ReadFileTool,
    SearchCodeTool,
)
from app.tools.create_artifact import CreateArtifactTool
from app.tools.current_time import CurrentTimeTool
from app.tools.read_document import ReadDocumentTool
from app.tools.registry import ToolRegistry
from app.tools.search_files import SearchFilesTool
from app.tools.search_memories import SearchMemoriesTool
from app.tools.tasks import CreateTaskTool, ListTasksTool
from app.voice.provider import MockVoiceProvider, VoiceProvider, WhisperCppProvider
from app.voice.session import VoiceService


@dataclass(slots=True)
class AppResources:
    settings: Settings
    database: AsyncEngine
    redis: Redis
    http_client: httpx.AsyncClient
    provider: LLMProvider
    task_repository: TaskRepository
    artifact_repository: ArtifactRepository
    run_repository: RunRepository
    event_repository: EventRepository
    event_bus: EventBus
    tool_registry: ToolRegistry
    agent_runtime: AgentRuntime
    readiness: ReadinessService
    background_tasks: set[asyncio.Task[AgentRun]]
    doc_repository: DocumentRepository
    embedder: LocalEmbeddingProvider
    doc_indexer: DocumentIndexer
    indexing_tasks: set[asyncio.Task[None]]
    memory_repository: MemoryRepository
    memory_extractor: MemoryExtractor
    voice_service: VoiceService
    code_repository: CodeRepository
    code_import_slots: asyncio.Semaphore

    @classmethod
    def create(cls, settings: Settings) -> "AppResources":
        database = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
        )
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        http_client = httpx.AsyncClient()
        provider = create_provider(settings, http_client)
        voice_provider: VoiceProvider = (
            MockVoiceProvider()
            if settings.nexus_voice_provider == "mock"
            else WhisperCppProvider(http_client, str(settings.nexus_whisper_base_url))
        )
        voice_service = VoiceService(
            voice_provider,
            max_sessions=settings.nexus_voice_max_sessions,
            max_seconds=settings.nexus_voice_max_seconds,
            timeout_seconds=settings.nexus_voice_timeout_seconds,
        )
        if settings.app_env == "test":
            task_repository: TaskRepository = InMemoryTaskRepository()
            artifact_repository: ArtifactRepository = InMemoryArtifactRepository()
            run_repository: RunRepository = InMemoryRunRepository()
            event_repository: EventRepository = InMemoryEventRepository()
            doc_repository: DocumentRepository = InMemoryDocumentRepository()
            memory_repository: MemoryRepository = InMemoryMemoryRepository()
            code_repository: CodeRepository = InMemoryCodeRepository()
        else:
            task_repository = SqlTaskRepository(database)
            artifact_repository = SqlArtifactRepository(database)
            run_repository = SqlRunRepository(database)
            event_repository = SqlEventRepository(database)
            doc_repository = SqlDocumentRepository(database)
            memory_repository = SqlMemoryRepository(database)
            code_repository = SqlCodeRepository(database)
        event_bus = EventBus(event_repository)
        embedder = LocalEmbeddingProvider()
        doc_indexer = DocumentIndexer(doc_repository, embedder)
        memory_extractor = MemoryExtractor(provider, memory_repository)
        tool_registry = ToolRegistry()
        tool_registry.register(CalculatorTool())
        tool_registry.register(CurrentTimeTool())
        tool_registry.register(CreateTaskTool(task_repository))
        tool_registry.register(ListTasksTool(task_repository))
        tool_registry.register(CreateArtifactTool(artifact_repository))
        tool_registry.register(SearchFilesTool(doc_repository, embedder))
        tool_registry.register(ReadDocumentTool(doc_repository))
        tool_registry.register(SearchMemoriesTool(memory_repository))
        tool_registry.register(ListRepositoriesTool(code_repository))
        tool_registry.register(SearchCodeTool(code_repository))
        tool_registry.register(DependencyGraphTool(code_repository))
        tool_registry.register(CallSitesTool(code_repository))
        tool_registry.register(ReadFileTool(code_repository))
        tool_registry.register(FindSymbolTool(code_repository))
        agent_runtime = AgentRuntime(
            Planner(provider, tool_registry),
            Executor(provider, tool_registry),
            tool_registry,
            run_repository,
            event_bus,
            memory_extractor=memory_extractor,
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
            artifact_repository=artifact_repository,
            run_repository=run_repository,
            event_repository=event_repository,
            event_bus=event_bus,
            tool_registry=tool_registry,
            agent_runtime=agent_runtime,
            readiness=readiness,
            background_tasks=set(),
            doc_repository=doc_repository,
            embedder=embedder,
            doc_indexer=doc_indexer,
            indexing_tasks=set(),
            memory_repository=memory_repository,
            memory_extractor=memory_extractor,
            voice_service=voice_service,
            code_repository=code_repository,
            code_import_slots=asyncio.Semaphore(2),
        )

    async def initialize(self) -> None:
        if self.settings.app_env != "test":
            await initialize_schema(self.database)
            await initialize_doc_schema(self.database)
            await initialize_memory_schema(self.database)

    def run_in_background(self, run: AgentRun) -> None:
        task = asyncio.create_task(self.agent_runtime.execute(run))
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    def run_indexing_in_background(self, doc: Document, content: bytes) -> None:
        async def _index() -> None:
            await self.doc_indexer.index(doc, content)

        task = asyncio.create_task(_index())
        self.indexing_tasks.add(task)
        task.add_done_callback(self.indexing_tasks.discard)

    async def close(self) -> None:
        for task in self.background_tasks:
            task.cancel()
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        for indexing_task in self.indexing_tasks:
            indexing_task.cancel()
        if self.indexing_tasks:
            await asyncio.gather(*self.indexing_tasks, return_exceptions=True)
        await self.agent_runtime.close()
        await self.http_client.aclose()
        await self.redis.aclose()
        await self.database.dispose()
