import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.code.indexer import MAX_ARCHIVE_BYTES, RepositoryImportError, index_archive
from app.code.models import RepositorySnapshot, RepositorySummary
from app.code.repository import summarize
from app.dependencies import get_resources
from app.storage.resources import AppResources

router = APIRouter(prefix="/repositories", tags=["code"])
Workspace = Annotated[str, Query(min_length=1, max_length=100)]
Resources = Annotated[AppResources, Depends(get_resources)]


@router.post("", status_code=201)
async def import_repository(
    file: Annotated[UploadFile, File()],
    resources: Resources,
    name: Annotated[str, Query(min_length=1, max_length=160)],
    user_id: Workspace = "local",
) -> RepositorySummary:
    if resources.code_import_slots.locked():
        raise HTTPException(
            status_code=503, detail="Repository import capacity reached."
        )
    await resources.code_import_slots.acquire()
    indexing: asyncio.Task[RepositorySnapshot] | None = None
    try:
        content = await file.read(MAX_ARCHIVE_BYTES + 1)
        if len(content) > MAX_ARCHIVE_BYTES:
            raise HTTPException(status_code=413, detail="Archive exceeds 5 MiB.")
        try:
            indexing = asyncio.create_task(
                asyncio.to_thread(index_archive, content, user_id=user_id, name=name)
            )

            def finished(task: asyncio.Task[RepositorySnapshot]) -> None:
                resources.code_import_slots.release()
                if not task.cancelled():
                    task.exception()

            indexing.add_done_callback(finished)
            # Request cancellation must not free capacity while its worker runs.
            snapshot = await asyncio.shield(indexing)
        except RepositoryImportError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        await resources.code_repository.create(snapshot)
        return summarize(snapshot)
    finally:
        if indexing is None:
            resources.code_import_slots.release()


@router.get("")
async def list_repositories(
    resources: Resources, user_id: Workspace = "local"
) -> list[RepositorySummary]:
    return await resources.code_repository.list_for_user(user_id)


async def _require(
    repository_id: str, resources: AppResources, user_id: str
) -> RepositorySnapshot:
    snapshot = await resources.code_repository.get(repository_id, user_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    return snapshot


@router.get("/{repository_id}/files")
async def list_files(
    repository_id: str, resources: Resources, user_id: Workspace = "local"
) -> dict[str, object]:
    snapshot = await _require(repository_id, resources, user_id)
    return {
        "repository_id": snapshot.id,
        "skipped_files": snapshot.skipped_files,
        "files": [file.model_dump(exclude={"content"}) for file in snapshot.files],
    }


@router.get("/{repository_id}/file")
async def read_file(
    repository_id: str,
    resources: Resources,
    path: Annotated[str, Query(min_length=1, max_length=300)],
    start_line: Annotated[int, Query(ge=1)] = 1,
    user_id: Workspace = "local",
) -> dict[str, object]:
    snapshot = await _require(repository_id, resources, user_id)
    source = next((file for file in snapshot.files if file.path == path), None)
    if source is None:
        raise HTTPException(status_code=404, detail="Source file not found.")
    lines = source.content.splitlines()
    excerpt = "\n".join(lines[start_line - 1 : start_line + 199])
    return {
        "path": path,
        "sha256": source.sha256,
        "start_line": start_line,
        "total_lines": len(lines),
        "content": excerpt[:20000],
        "truncated": len(excerpt) > 20000 or start_line + 199 < len(lines),
    }


@router.get("/{repository_id}/search")
async def search_code(
    repository_id: str,
    resources: Resources,
    query: Annotated[str, Query(min_length=1, max_length=100)],
    user_id: Workspace = "local",
) -> dict[str, object]:
    if not query.strip():
        raise HTTPException(status_code=422, detail="Search query cannot be blank.")
    snapshot = await _require(repository_id, resources, user_id)
    matches: list[dict[str, object]] = []
    for source in snapshot.files:
        for line, text in enumerate(source.content.splitlines(), start=1):
            if query.casefold() in text.casefold():
                if len(matches) == 20:
                    return {"matches": matches, "truncated": True}
                matches.append(
                    {
                        "path": source.path,
                        "line": line,
                        "text": text[:300],
                        "sha256": source.sha256,
                    }
                )
    return {"matches": matches, "truncated": False}
