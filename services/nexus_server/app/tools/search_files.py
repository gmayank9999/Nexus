"""search_files tool: semantic search over user documents."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.documents.embeddings import EmbeddingProvider
from app.documents.repository import DocumentRepository
from app.tools.base import PermissionLevel, Tool, ToolContext


class SearchFilesInput(BaseModel):
    query: str = Field(..., description="Natural-language search query")
    top_k: int = Field(5, ge=1, le=20, description="Number of results to return")


class SearchFilesTool(Tool):
    name = "search_files"
    description = (
        "Semantically search the user's uploaded documents. "
        "Returns the most relevant text snippets with source citations."
    )
    permission_level = PermissionLevel.READ_ONLY
    input_schema = SearchFilesInput

    def __init__(
        self,
        doc_repository: DocumentRepository,
        embedder: EmbeddingProvider,
    ) -> None:
        self._repo = doc_repository
        self._embedder = embedder

    async def execute(
        self, arguments: BaseModel, context: ToolContext
    ) -> dict[str, Any]:
        parsed = SearchFilesInput.model_validate(arguments)
        query_vecs = await self._embedder.embed([parsed.query])
        query_vec = query_vecs[0]
        results = await self._repo.search(
            context.user_id,
            query_vec,
            top_k=parsed.top_k,
            embedder=self._embedder,
        )
        if not results:
            return {"matches": [], "message": "No relevant documents found."}

        matches = [
            {
                "document_id": r.citation.document_id,
                "title": r.citation.title,
                "snippet": r.citation.snippet,
                "score": r.citation.score,
                "page": r.citation.page,
                "section": r.citation.section,
                "chunk_id": r.citation.chunk_id,
            }
            for r in results
        ]
        return {"matches": matches}
