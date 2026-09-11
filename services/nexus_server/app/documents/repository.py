"""Document and chunk repository with in-memory vector search."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.documents.embeddings import EmbeddingProvider
from app.documents.models import Citation, Document, DocumentChunk, SearchResult
from app.storage.doc_tables import document_chunks, documents


class DocumentRepository(ABC):
    @abstractmethod
    async def create(self, doc: Document) -> None: ...

    @abstractmethod
    async def get(self, doc_id: str) -> Document | None: ...

    @abstractmethod
    async def list_by_user(self, user_id: str) -> list[Document]: ...

    @abstractmethod
    async def update_status(
        self,
        doc_id: str,
        status: str,
        chunk_count: int | None = None,
        error: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def delete(self, doc_id: str) -> None: ...

    @abstractmethod
    async def save_chunks(self, chunks: list[DocumentChunk]) -> None: ...

    @abstractmethod
    async def get_chunks(self, doc_id: str) -> list[DocumentChunk]: ...

    @abstractmethod
    async def search(
        self,
        user_id: str,
        query_embedding: list[float],
        top_k: int,
        embedder: EmbeddingProvider,
    ) -> list[SearchResult]: ...


class InMemoryDocumentRepository(DocumentRepository):
    """Used in tests and development without a database."""

    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}
        self._chunks: dict[str, list[DocumentChunk]] = {}

    async def create(self, doc: Document) -> None:
        self._docs[doc.id] = doc

    async def get(self, doc_id: str) -> Document | None:
        return self._docs.get(doc_id)

    async def list_by_user(self, user_id: str) -> list[Document]:
        return [d for d in self._docs.values() if d.user_id == user_id]

    async def update_status(
        self,
        doc_id: str,
        status: str,
        chunk_count: int | None = None,
        error: str | None = None,
    ) -> None:
        if doc_id not in self._docs:
            return
        doc = self._docs[doc_id]
        self._docs[doc_id] = doc.model_copy(
            update={
                "status": status,
                "chunk_count": chunk_count
                if chunk_count is not None
                else doc.chunk_count,
                "error": error,
                "updated_at": datetime.now(UTC),
            }
        )

    async def delete(self, doc_id: str) -> None:
        self._docs.pop(doc_id, None)
        self._chunks.pop(doc_id, None)

    async def save_chunks(self, chunks: list[DocumentChunk]) -> None:
        for chunk in chunks:
            self._chunks.setdefault(chunk.document_id, []).append(chunk)

    async def get_chunks(self, doc_id: str) -> list[DocumentChunk]:
        return self._chunks.get(doc_id, [])

    async def search(
        self,
        user_id: str,
        query_embedding: list[float],
        top_k: int,
        embedder: EmbeddingProvider,
    ) -> list[SearchResult]:
        candidates: list[tuple[float, DocumentChunk, Document]] = []
        for doc in self._docs.values():
            if doc.user_id != user_id or doc.status != "indexed":
                continue
            for chunk in self._chunks.get(doc.id, []):
                if not chunk.embedding:
                    continue
                score = embedder.cosine_similarity(query_embedding, chunk.embedding)
                candidates.append((score, chunk, doc))

        candidates.sort(key=lambda t: t[0], reverse=True)
        results: list[SearchResult] = []
        for score, chunk, doc in candidates[:top_k]:
            results.append(
                SearchResult(
                    chunk=chunk,
                    citation=Citation(
                        document_id=doc.id,
                        chunk_id=chunk.id,
                        title=doc.title,
                        page=chunk.page,
                        section=chunk.section,
                        score=round(score, 4),
                        snippet=chunk.text[:200],
                    ),
                )
            )
        return results


class SqlDocumentRepository(DocumentRepository):
    """PostgreSQL-backed repository for production."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def create(self, doc: Document) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                insert(documents).values(
                    id=doc.id,
                    user_id=doc.user_id,
                    data=doc.model_dump_for_db(),
                    created_at=doc.created_at,
                )
            )

    async def get(self, doc_id: str) -> Document | None:
        async with self._engine.connect() as conn:
            row = await conn.execute(
                select(documents.c.data).where(documents.c.id == doc_id)
            )
            result = row.first()
            if result is None:
                return None
            return Document.model_validate(result[0])

    async def list_by_user(self, user_id: str) -> list[Document]:
        async with self._engine.connect() as conn:
            rows = await conn.execute(
                select(documents.c.data)
                .where(documents.c.user_id == user_id)
                .order_by(documents.c.created_at.desc())
            )
            return [Document.model_validate(r[0]) for r in rows]

    async def update_status(
        self,
        doc_id: str,
        status: str,
        chunk_count: int | None = None,
        error: str | None = None,
    ) -> None:
        doc = await self.get(doc_id)
        if doc is None:
            return
        updated = doc.model_copy(
            update={
                "status": status,
                "chunk_count": chunk_count
                if chunk_count is not None
                else doc.chunk_count,
                "error": error,
                "updated_at": datetime.now(UTC),
            }
        )
        async with self._engine.begin() as conn:
            await conn.execute(
                update(documents)
                .where(documents.c.id == doc_id)
                .values(data=updated.model_dump_for_db())
            )

    async def delete(self, doc_id: str) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                delete(document_chunks).where(document_chunks.c.document_id == doc_id)
            )
            await conn.execute(delete(documents).where(documents.c.id == doc_id))

    async def save_chunks(self, chunks: list[DocumentChunk]) -> None:
        if not chunks:
            return
        async with self._engine.begin() as conn:
            for chunk in chunks:
                await conn.execute(
                    insert(document_chunks).values(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        chunk_index=chunk.index,
                        text=chunk.text,
                        page=chunk.page,
                        section=chunk.section,
                        embedding_json=json.dumps(chunk.embedding)
                        if chunk.embedding
                        else None,
                    )
                )

    async def get_chunks(self, doc_id: str) -> list[DocumentChunk]:
        async with self._engine.connect() as conn:
            rows = await conn.execute(
                select(document_chunks)
                .where(document_chunks.c.document_id == doc_id)
                .order_by(document_chunks.c.chunk_index)
            )
            result: list[DocumentChunk] = []
            for row in rows:
                emb = json.loads(row.embedding_json) if row.embedding_json else None
                result.append(
                    DocumentChunk(
                        id=row.id,
                        document_id=row.document_id,
                        index=row.chunk_index,
                        text=row.text,
                        page=row.page,
                        section=row.section,
                        embedding=emb,
                    )
                )
            return result

    async def search(
        self,
        user_id: str,
        query_embedding: list[float],
        top_k: int,
        embedder: EmbeddingProvider,
    ) -> list[SearchResult]:
        # In-process cosine search — acceptable for MVP scale.
        # Replace with pgvector in a future optimization pass.
        async with self._engine.connect() as conn:
            rows = await conn.execute(
                select(
                    documents.c.id,
                    documents.c.data,
                    document_chunks,
                )
                .join(
                    document_chunks,
                    documents.c.id == document_chunks.c.document_id,
                )
                .where(
                    documents.c.user_id == user_id,
                )
            )
            all_rows = rows.fetchall()

        candidates: list[tuple[float, DocumentChunk, str, str]] = []
        for row in all_rows:
            doc_data = row[1]
            if isinstance(doc_data, dict) and doc_data.get("status") != "indexed":
                continue
            emb = json.loads(row.embedding_json) if row.embedding_json else None
            if not emb:
                continue
            score = embedder.cosine_similarity(query_embedding, emb)
            chunk = DocumentChunk(
                id=row.id,
                document_id=row.document_id,
                index=row.chunk_index,
                text=row.text,
                page=row.page,
                section=row.section,
                embedding=emb,
            )
            title = doc_data.get("title", "") if isinstance(doc_data, dict) else ""
            candidates.append((score, chunk, row[0], title))

        candidates.sort(key=lambda t: t[0], reverse=True)
        results: list[SearchResult] = []
        for score, chunk, doc_id, title in candidates[:top_k]:
            results.append(
                SearchResult(
                    chunk=chunk,
                    citation=Citation(
                        document_id=doc_id,
                        chunk_id=chunk.id,
                        title=title,
                        page=chunk.page,
                        section=chunk.section,
                        score=round(score, 4),
                        snippet=chunk.text[:200],
                    ),
                )
            )
        return results
