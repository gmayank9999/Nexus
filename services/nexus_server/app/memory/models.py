"""Memory domain models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MemoryCategory(StrEnum):
    USER_PREFERENCE = "user_preference"
    USER_GOAL = "user_goal"
    USER_FACT = "user_fact"
    PROJECT_CONTEXT = "project_context"
    LEARNING_STATE = "learning_state"
    TASK_CONTEXT = "task_context"


class Memory(BaseModel):
    """A single unit of long-term memory."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str
    category: MemoryCategory
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = "agent"  # 'agent' | 'user'
    run_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def model_dump_for_db(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class MemoryCandidate(BaseModel):
    """Raw candidate produced by the memory extractor before validation."""

    category: MemoryCategory
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
