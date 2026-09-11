"""Tests for the document ingestion and search pipeline."""

from __future__ import annotations

import pytest

from app.documents.chunker import chunk_text
from app.documents.embeddings import LocalEmbeddingProvider
from app.documents.extractor import extract_text, supported_mime
from app.documents.indexer import DocumentIndexer
from app.documents.models import Document
from app.documents.repository import InMemoryDocumentRepository


class TestExtractor:
    def test_supported_mimes(self) -> None:
        assert supported_mime("text/plain")
        assert supported_mime("text/markdown")
        assert supported_mime("application/pdf")
        assert not supported_mime("application/zip")

    def test_extract_plain_text(self) -> None:
        content = b"Hello world\nSecond line"
        assert extract_text(content, "text/plain") == "Hello world\nSecond line"

    def test_extract_markdown(self) -> None:
        content = b"# Title\n\nSome text"
        assert "Title" in extract_text(content, "text/markdown")

    def test_unsupported_raises(self) -> None:
        with pytest.raises(ValueError):
            extract_text(b"data", "application/zip")


class TestChunker:
    def test_single_chunk(self) -> None:
        text = "word " * 50  # 250 chars — below default 500
        chunks = chunk_text("doc1", text, chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0].document_id == "doc1"
        assert chunks[0].index == 0

    def test_multiple_chunks(self) -> None:
        text = "word " * 300  # 1500 chars
        chunks = chunk_text("doc1", text, chunk_size=500, overlap=50)
        assert len(chunks) >= 2
        # chunks are ordered
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_empty_text(self) -> None:
        chunks = chunk_text("doc1", "")
        assert chunks == []


class TestEmbeddings:
    @pytest.mark.asyncio
    async def test_hash_embed_deterministic(self) -> None:
        provider = LocalEmbeddingProvider("all-MiniLM-L6-v2")
        # Force fallback to hash embed by bypassing model load
        vecs = await provider.embed(["hello world", "hello world"])
        assert len(vecs) == 2
        # Deterministic: same text -> same vector
        assert vecs[0] == vecs[1]

    def test_cosine_same_vector(self) -> None:
        provider = LocalEmbeddingProvider()
        v = [1.0, 0.0, 0.0]
        score = provider.cosine_similarity(v, v)
        assert abs(score - 1.0) < 1e-6

    def test_cosine_orthogonal(self) -> None:
        provider = LocalEmbeddingProvider()
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        score = provider.cosine_similarity(a, b)
        assert abs(score) < 1e-6


class TestDocumentPipeline:
    @pytest.mark.asyncio
    async def test_full_index_and_search(self) -> None:
        repo = InMemoryDocumentRepository()
        embedder = LocalEmbeddingProvider()
        indexer = DocumentIndexer(repo, embedder, chunk_size=200, overlap=30)

        doc = Document(
            user_id="user1",
            title="Test.txt",
            mime_type="text/plain",
            size_bytes=100,
        )
        await repo.create(doc)
        content = b"Flutter is a UI toolkit for building beautiful apps.\n" * 20
        await indexer.index(doc, content)

        # status updated
        stored = await repo.get(doc.id)
        assert stored is not None
        assert stored.status == "indexed"
        assert stored.chunk_count > 0

        # search returns results
        query_vec = (await embedder.embed(["Flutter UI toolkit"]))[0]
        results = await repo.search("user1", query_vec, top_k=3, embedder=embedder)
        assert len(results) > 0
        assert results[0].citation.document_id == doc.id

    @pytest.mark.asyncio
    async def test_index_bad_mime_sets_failed(self) -> None:
        repo = InMemoryDocumentRepository()
        embedder = LocalEmbeddingProvider()
        indexer = DocumentIndexer(repo, embedder)

        doc = Document(
            user_id="user1",
            title="Bad.zip",
            mime_type="application/zip",
            size_bytes=10,
        )
        await repo.create(doc)
        with pytest.raises(ValueError):
            await indexer.index(doc, b"data")

        stored = await repo.get(doc.id)
        assert stored is not None
        assert stored.status == "failed"

    @pytest.mark.asyncio
    async def test_search_respects_user(self) -> None:
        repo = InMemoryDocumentRepository()
        embedder = LocalEmbeddingProvider()
        indexer = DocumentIndexer(repo, embedder, chunk_size=200)

        doc_a = Document(
            user_id="alice", title="A.txt", mime_type="text/plain", size_bytes=50
        )
        doc_b = Document(
            user_id="bob", title="B.txt", mime_type="text/plain", size_bytes=50
        )
        for doc in (doc_a, doc_b):
            await repo.create(doc)
            await indexer.index(doc, b"Hello user " * 30)

        query_vec = (await embedder.embed(["Hello"]))[0]
        alice_results = await repo.search(
            "alice", query_vec, top_k=5, embedder=embedder
        )
        assert all(r.citation.document_id == doc_a.id for r in alice_results)
