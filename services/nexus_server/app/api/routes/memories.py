"""REST API routes for the memory system."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import get_resources
from app.memory.models import Memory, MemoryCategory
from app.storage.resources import AppResources

router = APIRouter(prefix="/memories", tags=["memories"])


class CreateMemoryRequest(BaseModel):
    category: MemoryCategory
    content: str = Field(min_length=1, max_length=500)
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
) -> MemoryResponse:
    memory = Memory(
        user_id="default",
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
    min_confidence: float = 0.0,
) -> list[MemoryResponse]:
    mems = await resources.memory_repository.list_for_user(
        "default",
        category=category,
        min_confidence=min_confidence,
    )
    return [MemoryResponse.from_memory(m) for m in mems]


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    resources: Annotated[AppResources, Depends(get_resources)],
) -> None:
    m = await resources.memory_repository.get(memory_id)
    if m is None or m.user_id != "default":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found"
        )
    await resources.memory_repository.delete(memory_id)
