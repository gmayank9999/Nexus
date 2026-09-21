from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.routes.documents import read_document_source
from app.documents.embeddings import LocalEmbeddingProvider
from app.documents.models import Document, DocumentChunk
from app.documents.repository import InMemoryDocumentRepository, SqlDocumentRepository
from app.storage.doc_tables import initialize_doc_schema


@pytest.fixture(params=["memory", "sql"])
async def repository(request: pytest.FixtureRequest, tmp_path: Path):
    if request.param == "memory":
        yield InMemoryDocumentRepository()
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'sources.db'}")
        await initialize_doc_schema(engine)
        try:
            yield SqlDocumentRepository(engine)
        finally:
            await engine.dispose()


async def test_exact_source_lookup_is_bounded_and_excludes_embeddings(
    repository,
) -> None:
    doc = Document(
        user_id="local",
        title="Resume",
        mime_type="text/plain",
        size_bytes=1,
        status="indexed",
        chunk_count=2,
    )
    await repository.create(doc)
    chunks = [
        DocumentChunk(
            document_id=doc.id,
            index=i,
            text="x" * 20001,
            embedding=[1.0, 0.0],
            page=2,
            section="Projects",
        )
        for i in range(2)
    ]
    await repository.save_chunks(chunks)
    resources = SimpleNamespace(doc_repository=repository)
    source = await read_document_source(doc.id, resources, chunk_id=chunks[1].id)
    assert source.chunk_id == chunks[1].id and source.chunk_index == 1
    assert len(source.text) == 20000 and source.truncated
    assert source.page == 2 and "embedding" not in source.model_dump()
    assert (
        await read_document_source(doc.id, resources, chunk_index=0)
    ).chunk_id == chunks[0].id
    for user, chunk_id in [("other", chunks[0].id), ("local", "missing")]:
        with pytest.raises(HTTPException) as error:
            await read_document_source(
                doc.id, resources, chunk_id=chunk_id, user_id=user
            )
        assert error.value.status_code == 404
    # SQL joins must not confuse the document and chunk IDs in retrieval citations.
    result = await repository.search("local", [1.0, 0.0], 2, LocalEmbeddingProvider())
    assert {match.citation.chunk_id for match in result} == {c.id for c in chunks}
    assert all(match.citation.document_id == doc.id for match in result)
    await repository.delete(doc.id)
    with pytest.raises(HTTPException) as error:
        await read_document_source(doc.id, resources)
    assert error.value.status_code == 404


async def test_pending_and_foreign_chunks_cannot_be_read(repository) -> None:
    doc = Document(
        user_id="local", title="Pending", mime_type="text/plain", size_bytes=1
    )
    await repository.create(doc)
    resources = SimpleNamespace(doc_repository=repository)
    with pytest.raises(HTTPException) as error:
        await read_document_source(doc.id, resources)
    assert error.value.status_code == 409
    await repository.update_status(doc.id, "indexed", chunk_count=1)
    other = Document(
        user_id="other", title="Other", mime_type="text/plain", size_bytes=1
    )
    await repository.create(other)
    foreign = DocumentChunk(document_id=other.id, index=0, text="private")
    await repository.save_chunks([foreign])
    with pytest.raises(HTTPException) as error:
        await read_document_source(doc.id, resources, chunk_id=foreign.id)
    assert error.value.status_code == 404
