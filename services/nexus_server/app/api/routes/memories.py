"""REST API routes for the memory system."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from app.dependencies import get_resources
from app.memory.models import Memory, MemoryCategory
from app.storage.resources import AppResources

router = APIRouter(prefix="/memories", tags=["memories"])


class EditMemoryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=500)

    @field_validator("content")
    @classmethod
    def nonblank_content(cls, content: str) -> str:
        if not content.strip():
            raise ValueError("Memory content cannot be blank.")
        return content.strip()


class CreateMemoryRequest(EditMemoryRequest):
    category: MemoryCategory
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class MemoryResponse(BaseModel):
    id: str
    category: str
    content: str
    confidence: float
    source: str
    run_id: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_memory(cls, m: Memory) -> MemoryResponse:
        return cls(
            id=m.id,
            category=m.category,
            content=m.content,
            confidence=m.confidence,
            source=m.source,
            run_id=m.run_id,
            created_at=m.created_at.isoformat(),
            updated_at=m.updated_at.isoformat(),
        )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_memory(
    body: CreateMemoryRequest,
    resources: Annotated[AppResources, Depends(get_resources)],
    user_id: Annotated[str, Query(min_length=1, max_length=100)] = "local",
) -> MemoryResponse:
    memory = Memory(
        user_id=user_id,
        category=body.category,
        content=body.content,
        confidence=body.confidence,
        source="user",
    )
    await resources.memory_repository.create(memory)
    return MemoryResponse.from_memory(memory)


@router.get("")
async def list_memories(
    resources: Annotated[AppResources, Depends(get_resources)],
    category: MemoryCategory | None = None,
    min_confidence: Annotated[float, Query(ge=0, le=1)] = 0.0,
    user_id: Annotated[str, Query(min_length=1, max_length=100)] = "local",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[MemoryResponse]:
    mems = await resources.memory_repository.list_for_user(
        user_id,
        category=category,
        min_confidence=min_confidence,
        limit=limit,
    )
    return [MemoryResponse.from_memory(m) for m in mems]


@router.patch("/{memory_id}")
async def edit_memory(
    memory_id: str,
    body: EditMemoryRequest,
    resources: Annotated[AppResources, Depends(get_resources)],
    user_id: Annotated[str, Query(min_length=1, max_length=100)] = "local",
) -> MemoryResponse:
    memory = await resources.memory_repository.edit_content(
        memory_id, user_id, body.content
    )
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return MemoryResponse.from_memory(memory)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    resources: Annotated[AppResources, Depends(get_resources)],
    user_id: Annotated[str, Query(min_length=1, max_length=100)] = "local",
) -> None:
    deleted = await resources.memory_repository.delete(memory_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found"
        )
