"""REST API routes for document upload, listing, and deletion."""

from __future__ import annotations

import mimetypes
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.dependencies import get_resources
from app.documents.extractor import supported_mime
from app.documents.models import Document
from app.storage.resources import AppResources

router = APIRouter(prefix="/documents", tags=["documents"])

_MAX_SIZE = 20 * 1024 * 1024  # 20 MB
Workspace = Annotated[str, Query(min_length=1, max_length=100)]


class DocumentResponse(BaseModel):
    id: str
    title: str
    status: str
    mime_type: str
    size_bytes: int
    chunk_count: int
    error: str | None

    @classmethod
    def from_doc(cls, doc: Document) -> DocumentResponse:
        return cls(
            id=doc.id,
            title=doc.title,
            status=doc.status,
            mime_type=doc.mime_type,
            size_bytes=doc.size_bytes,
            chunk_count=doc.chunk_count,
            error="Document indexing failed." if doc.error else None,
        )


class DocumentSource(BaseModel):
    document_id: str
    title: str
    chunk_id: str
    chunk_index: int
    chunk_count: int
    text: str
    page: int | None
    section: str | None
    truncated: bool


@router.get("/{doc_id}/source")
async def read_document_source(
    doc_id: str,
    resources: Annotated[AppResources, Depends(get_resources)],
    chunk_id: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    chunk_index: Annotated[int, Query(ge=0)] = 0,
    user_id: Workspace = "local",
) -> DocumentSource:
    doc = await resources.doc_repository.get(doc_id)
    if doc is None or doc.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "indexed":
        raise HTTPException(status_code=409, detail="Document is not indexed")
    chunk = await resources.doc_repository.get_chunk(
        doc_id, chunk_id=chunk_id, index=chunk_index
    )
    if chunk is None:
        raise HTTPException(status_code=404, detail="Source chunk not found")
    return DocumentSource(
        document_id=doc.id,
        title=doc.title,
        chunk_id=chunk.id,
        chunk_index=chunk.index,
        chunk_count=doc.chunk_count,
        text=chunk.text[:20000],
        page=chunk.page,
        section=chunk.section[:200] if chunk.section else None,
        truncated=len(chunk.text) > 20000,
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: Annotated[UploadFile, File()],
    resources: Annotated[AppResources, Depends(get_resources)],
    user_id: Workspace = "local",
) -> DocumentResponse:
    content = await file.read(_MAX_SIZE + 1)
    if len(content) > _MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="File exceeds 20 MB limit",
        )

    # Resolve MIME type
    mime = file.content_type or ""
    if not mime or mime == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(file.filename or "")
        mime = guessed or mime

    if not supported_mime(mime):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {mime}. Supported: PDF, TXT, MD, DOCX",
        )

    doc = Document(
        user_id=user_id,
        title=file.filename or "Untitled",
        mime_type=mime,
        size_bytes=len(content),
    )
    await resources.doc_repository.create(doc)

    # Run indexing in background
    resources.run_indexing_in_background(doc, content)

    return DocumentResponse.from_doc(doc)


@router.get("")
async def list_documents(
    resources: Annotated[AppResources, Depends(get_resources)],
    user_id: Workspace = "local",
) -> list[DocumentResponse]:
    docs = await resources.doc_repository.list_by_user(user_id)
    return [DocumentResponse.from_doc(d) for d in docs]


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    resources: Annotated[AppResources, Depends(get_resources)],
    user_id: Workspace = "local",
) -> DocumentResponse:
    doc = await resources.doc_repository.get(doc_id)
    if doc is None or doc.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return DocumentResponse.from_doc(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: str,
    resources: Annotated[AppResources, Depends(get_resources)],
    user_id: Workspace = "local",
) -> None:
    doc = await resources.doc_repository.get(doc_id)
    if doc is None or doc.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    await resources.doc_repository.delete(doc_id)
