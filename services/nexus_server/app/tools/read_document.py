"""read_document tool: fetch a specific chunk from a document."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.documents.repository import DocumentRepository
from app.tools.base import PermissionLevel, Tool, ToolContext


class ReadDocumentInput(BaseModel):
    document_id: str = Field(..., description="ID of the document to read")
    chunk_index: int | None = Field(
        None, description="Optional zero-based chunk index; omit to read all"
    )


class ReadDocumentTool(Tool):
    name = "read_document"
    description = (
        "Read the text content of an uploaded document. "
        "Specify chunk_index to read a single window, or omit it to get all text."
    )
    permission_level = PermissionLevel.READ_ONLY
    input_schema = ReadDocumentInput

    def __init__(self, doc_repository: DocumentRepository) -> None:
        self._repo = doc_repository

    async def execute(
        self, arguments: BaseModel, context: ToolContext
    ) -> dict[str, Any]:
        parsed = ReadDocumentInput.model_validate(arguments)
        doc = await self._repo.get(parsed.document_id)
        if doc is None:
            return {"error": f"Document {parsed.document_id!r} not found"}
        if doc.user_id != context.user_id:
            return {"error": "Access denied"}

        chunks = await self._repo.get_chunks(parsed.document_id)
        if not chunks:
            return {"text": "", "message": "Document has no indexed content."}

        if parsed.chunk_index is not None:
            if parsed.chunk_index >= len(chunks):
                return {"error": f"Chunk index {parsed.chunk_index} out of range"}
            chunk = chunks[parsed.chunk_index]
            return {
                "document_id": doc.id,
                "title": doc.title,
                "chunk_index": chunk.index,
                "text": chunk.text,
                "page": chunk.page,
            }

        full_text = "\n\n".join(c.text for c in chunks)
        return {
            "document_id": doc.id,
            "title": doc.title,
            "chunk_count": len(chunks),
            "text": full_text[:4000],  # cap to avoid context overflow
        }
