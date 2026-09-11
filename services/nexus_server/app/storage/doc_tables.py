"""SQLAlchemy table definitions for document storage."""

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine

doc_metadata = MetaData()

documents = Table(
    "documents",
    doc_metadata,
    Column("id", String(80), primary_key=True),
    Column("user_id", String(100), nullable=False),
    Column("data", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("ix_documents_user", documents.c.user_id)

document_chunks = Table(
    "document_chunks",
    doc_metadata,
    Column("id", String(80), primary_key=True),
    Column("document_id", String(80), nullable=False),
    Column("chunk_index", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("page", Integer, nullable=True),
    Column("section", String(200), nullable=True),
    Column("embedding_json", Text, nullable=True),
)
Index(
    "ix_document_chunks_doc",
    document_chunks.c.document_id,
    document_chunks.c.chunk_index,
)


async def initialize_doc_schema(database: AsyncEngine) -> None:
    async with database.begin() as connection:
        await connection.run_sync(doc_metadata.create_all)
