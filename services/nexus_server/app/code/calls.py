"""Bounded syntactic call evidence, not a resolved execution graph."""

from pydantic import BaseModel, Field

from app.code.models import CodeCall, RepositorySnapshot


class CallEvidence(CodeCall):
    path: str
    sha256: str


class CallSites(BaseModel):
    repository_id: str
    calls: list[CallEvidence] = Field(default_factory=list)
    truncated: bool = False
    incomplete_index: bool = False
    semantics: str = (
        "Syntactic call sites in lexical scopes, not resolved targets or execution "
        "order. Defaults and decorators can execute outside their lexical scope."
    )


def call_sites(snapshot: RepositorySnapshot) -> CallSites:
    result = CallSites(
        repository_id=snapshot.id,
        incomplete_index=bool(snapshot.skipped_files)
        or any(
            file.language != "python"
            or not file.calls_indexed
            or file.parse_error
            or file.index_truncated
            or file.calls_truncated
            for file in snapshot.files
        ),
    )
    for source in sorted(snapshot.files, key=lambda file: file.path):
        for call in source.calls:
            if len(result.calls) == 500:
                result.truncated = True
                return result
            result.calls.append(
                CallEvidence(
                    **call.model_dump(),
                    path=source.path,
                    sha256=source.sha256,
                )
            )
        result.truncated = result.truncated or source.calls_truncated
    return result
