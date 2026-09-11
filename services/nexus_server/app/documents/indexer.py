"""Document indexing pipeline: extract → chunk → embed → store."""

from __future__ import annotations

import logging

from app.documents.chunker import chunk_text
from app.documents.embeddings import EmbeddingProvider
from app.documents.extractor import extract_text
from app.documents.models import Document
from app.documents.repository import DocumentRepository

logger = logging.getLogger(__name__)


class DocumentIndexer:
    """Orchestrates extraction, chunking, and embedding for a single document."""

    def __init__(
        self,
        repository: DocumentRepository,
        embedder: EmbeddingProvider,
        chunk_size: int = 500,
        overlap: int = 80,
    ) -> None:
        self._repo = repository
        self._embedder = embedder
        self._chunk_size = chunk_size
        self._overlap = overlap

    async def index(self, doc: Document, content: bytes) -> None:
        """Run the full pipeline for *doc*.  Updates status in the repository."""
        await self._repo.update_status(doc.id, "indexing")
        try:
            text = extract_text(content, doc.mime_type)
            chunks = chunk_text(doc.id, text, self._chunk_size, self._overlap)

            if chunks:
                texts = [c.text for c in chunks]
                embeddings = await self._embedder.embed(texts)
                for chunk, embedding in zip(chunks, embeddings, strict=True):
                    chunk.embedding = embedding

            await self._repo.save_chunks(chunks)
            await self._repo.update_status(doc.id, "indexed", chunk_count=len(chunks))
            logger.info("Indexed document %s (%d chunks)", doc.id, len(chunks))
        except Exception as exc:
            logger.exception("Indexing failed for document %s", doc.id)
            await self._repo.update_status(doc.id, "failed", error=str(exc))
            raise
