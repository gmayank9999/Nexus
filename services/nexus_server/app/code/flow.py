"""Bounded navigation of lexical calls and same-file declaration candidates."""

from collections import deque

from pydantic import BaseModel, Field

from app.code.models import CodeSymbol, RepositorySnapshot

MAX_NODES = 25
MAX_EDGES = 100


class FlowNode(BaseModel):
    id: str
    path: str
    name: str
    line: int
    end_line: int
    sha256: str


class FlowEdge(BaseModel):
    source: str
    target: str | None = None
    callee: str
    line: int
    column: int
    resolution: str


class SourceFlow(BaseModel):
    repository_id: str
    entry: str
    nodes: list[FlowNode] = Field(default_factory=list)
    edges: list[FlowEdge] = Field(default_factory=list)
    truncated: bool = False
    incomplete_index: bool = False
    max_depth: int
    semantics: str = (
        "Lexical call evidence with same-file top-level function name candidates. "
        "Candidate links are NOT verified bindings, execution order, or runtime paths. "
        "Parameters, assignments, imports, decorators, and dynamic dispatch can change "
        "targets. Defaults and decorators may execute outside their lexical scope."
    )


def source_flow(
    snapshot: RepositorySnapshot,
    path: str,
    symbol: str,
    max_depth: int = 3,
) -> SourceFlow:
    if not 0 <= max_depth <= 5:
        raise ValueError("Depth must be between 0 and 5.")
    source = next((file for file in snapshot.files if file.path == path), None)
    if source is None:
        raise LookupError("Source file not found.")
    entries = [
        item
        for item in source.symbols
        if item.name == symbol and item.kind == "function"
    ]
    if len(entries) != 1:
        raise ValueError("Choose an exact, uniquely indexed Python function name.")
    entry = entries[0]
    if len(entry.name) > 300:
        raise ValueError("Function name exceeds the supported 300 characters.")

    def node(item: CodeSymbol) -> FlowNode:
        return FlowNode(
            id=f"{source.path}:{item.line}",
            path=source.path,
            name=item.name,
            line=item.line,
            end_line=item.end_line,
            sha256=source.sha256,
        )

    root = node(entry)
    result = SourceFlow(
        repository_id=snapshot.id,
        entry=root.id,
        nodes=[root],
        max_depth=max_depth,
        incomplete_index=(
            not source.calls_indexed
            or source.parse_error
            or source.index_truncated
            or source.calls_truncated
        ),
    )
    candidates: dict[str, list[CodeSymbol]] = {}
    for item in source.symbols:
        if item.kind == "function" and "." not in item.name:
            candidates.setdefault(item.name, []).append(item)
    pending = deque([(entry, 0)])
    visited = {root.id}
    while pending:
        current, depth = pending.popleft()
        for call in source.calls:
            if call.scope != current.name:
                continue
            if len(result.edges) == MAX_EDGES:
                result.truncated = True
                return result
            edge = FlowEdge(
                source=node(current).id,
                callee=call.callee,
                line=call.line,
                column=call.column,
                resolution="unresolved",
            )
            matches = candidates.get(call.callee, [])
            if call.label_truncated:
                edge.resolution = "truncated_label"
            elif call.dynamic or "." in call.callee:
                edge.resolution = "dynamic_or_attribute"
            elif len(matches) > 1:
                edge.resolution = "ambiguous_declaration"
            elif len(matches) == 1:
                target = node(matches[0])
                if target.id in visited:
                    edge.target = target.id
                    edge.resolution = "same_file_name_candidate"
                elif depth >= max_depth or len(visited) == MAX_NODES:
                    edge.resolution = "expansion_limit"
                    result.truncated = True
                else:
                    edge.target = target.id
                    edge.resolution = "same_file_name_candidate"
                    visited.add(target.id)
                    result.nodes.append(target)
                    pending.append((matches[0], depth + 1))
            result.edges.append(edge)
    return result
