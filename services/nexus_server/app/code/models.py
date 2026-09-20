from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class CodeSymbol(BaseModel):
    name: str
    kind: str
    line: int
    end_line: int


class CodeImport(BaseModel):
    module: str
    line: int


class SourceFile(BaseModel):
    path: str
    language: str
    content: str
    sha256: str
    symbols: list[CodeSymbol] = Field(default_factory=list)
    imports: list[CodeImport] = Field(default_factory=list)
    parse_error: bool = False
    index_truncated: bool = False


class RepositorySnapshot(BaseModel):
    id: str = Field(default_factory=lambda: f"repo_{uuid4().hex}")
    user_id: str
    name: str
    archive_sha256: str
    files: list[SourceFile]
    skipped_files: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RepositorySummary(BaseModel):
    id: str
    name: str
    file_count: int
    created_at: datetime
