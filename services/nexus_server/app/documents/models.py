"""Domain models for documents, chunks, and citations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """A text chunk from a document with optional embedding."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    document_id: str
    index: int
    text: str
    page: int | None = None
    section: str | None = None
    embedding: list[float] | None = None


class Document(BaseModel):
    """Indexed document with metadata."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str
    title: str
    mime_type: str
    size_bytes: int
    chunk_count: int = 0
    status: str = "pending"  # pending | indexing | indexed | failed
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def model_dump_for_db(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class Citation(BaseModel):
    """Source attribution from a RAG retrieval."""

    document_id: str
    chunk_id: str
    title: str
    page: int | None
    section: str | None
    score: float
    snippet: str


class SearchResult(BaseModel):
    """A single document chunk retrieval result."""

    chunk: DocumentChunk
    citation: Citation
