"""Conservative declared-module graph; no imports or runtime code are executed."""

from pathlib import PurePosixPath

from pydantic import BaseModel, Field

from app.code.models import RepositorySnapshot

MAX_EDGES = 500


class DependencyEdge(BaseModel):
    source: str
    target: str | None
    module: str
    module_truncated: bool = False
    line: int
    source_sha256: str
    resolution: str


class DependencyGraph(BaseModel):
    repository_id: str
    source_root: str
    nodes: list[str]
    edges: list[DependencyEdge] = Field(default_factory=list)
    truncated: bool = False
    incomplete_index: bool = False
    semantics: str = "Declared Python modules only; not runtime or call relationships."


def dependency_graph(
    snapshot: RepositorySnapshot, source_root: str = ""
) -> DependencyGraph:
    if source_root and (
        len(source_root) > 300
        or "\\" in source_root
        or ":" in source_root
        or any(part in {"", ".", ".."} for part in source_root.split("/"))
        or any(ord(char) < 32 or ord(char) == 127 for char in source_root)
    ):
        raise ValueError("Source root must be a relative snapshot directory.")
    prefix = f"{source_root}/" if source_root else ""
    sources = sorted(
        (source for source in snapshot.files if source.path.startswith(prefix)),
        key=lambda source: source.path,
    )
    if source_root and not sources:
        raise ValueError("Source root is not present in the snapshot.")
    python_paths = {source.path for source in sources if source.language == "python"}
    graph = DependencyGraph(
        repository_id=snapshot.id,
        source_root=source_root,
        nodes=sorted(python_paths),
        incomplete_index=bool(snapshot.skipped_files)
        or any(
            source.language != "python" or source.parse_error or source.index_truncated
            for source in sources
        ),
    )
    for source in sources:
        if source.language != "python":
            continue
        for item in source.imports:
            if len(graph.edges) == MAX_EDGES:
                graph.truncated = True
                return graph
            module = item.module
            levels = len(module) - len(module.lstrip("."))
            tail = module[levels:]
            relative = PurePosixPath(source.path[len(prefix) :]).parent.parts
            target = None
            resolution = "unresolved"
            if levels and (not relative or levels > len(relative)):
                resolution = "relative_beyond_root"
            elif not tail:
                # Older indexes do not retain imported member names. Do not
                # invent a submodule edge for `from . import something`.
                resolution = "relative_members_unresolved"
            else:
                parts = (
                    [*relative[: len(relative) - levels + 1], *tail.split(".")]
                    if levels
                    else tail.split(".")
                )
                stem = prefix + "/".join(parts)
                candidates = [
                    path
                    for path in (f"{stem}.py", f"{stem}/__init__.py")
                    if path in python_paths
                ]
                if len(candidates) == 1:
                    target = candidates[0]
                    resolution = "local_declared_module"
                elif len(candidates) > 1:
                    resolution = "ambiguous"
            graph.edges.append(
                DependencyEdge(
                    source=source.path,
                    target=target,
                    module=module[:300],
                    module_truncated=len(module) > 300,
                    line=item.line,
                    source_sha256=source.sha256,
                    resolution=resolution,
                )
            )
    return graph
