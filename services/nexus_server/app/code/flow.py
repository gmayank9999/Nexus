"""Bounded navigation of lexical calls and local/imported declaration candidates."""

from collections import deque

from pydantic import BaseModel, Field

from app.code.flow_links import declaration_candidates, flow_sources, partial
from app.code.models import CodeSymbol, RepositorySnapshot, SourceFile

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
    source_root: str = ""
    semantics: str = (
        "Lexical call evidence with local and explicitly imported function "
        "name candidates. "
        "Candidate links are NOT verified bindings, execution order, or runtime paths. "
        "Parameters, assignments, imports, decorators, and dynamic dispatch can change "
        "targets. Defaults and decorators may execute outside their lexical scope."
    )


def source_flow(
    snapshot: RepositorySnapshot,
    path: str,
    symbol: str,
    max_depth: int = 3,
    source_root: str = "",
) -> SourceFlow:
    if not 0 <= max_depth <= 5:
        raise ValueError("Depth must be between 0 and 5.")
    files = flow_sources(snapshot.files, source_root)
    source = files.get(path)
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

    def node(file: SourceFile, item: CodeSymbol) -> FlowNode:
        return FlowNode(
            id=f"{file.path}:{item.line}",
            path=file.path,
            name=item.name,
            line=item.line,
            end_line=item.end_line,
            sha256=file.sha256,
        )

    root = node(source, entry)
    result = SourceFlow(
        repository_id=snapshot.id,
        entry=root.id,
        nodes=[root],
        max_depth=max_depth,
        source_root=source_root,
        incomplete_index=partial(source),
    )
    pending = deque([(source, entry, 0)])
    visited = {root.id}
    while pending:
        current_file, current, depth = pending.popleft()
        result.incomplete_index = result.incomplete_index or partial(current_file)
        for call in current_file.calls:
            if call.scope != current.name:
                continue
            if len(result.edges) == MAX_EDGES:
                result.truncated = True
                return result
            edge = FlowEdge(
                source=node(current_file, current).id,
                callee=call.callee,
                line=call.line,
                column=call.column,
                resolution="unresolved",
            )
            matches, resolution, incomplete = declaration_candidates(
                current_file,
                call.callee,
                files,
                source_root,
            )
            result.incomplete_index = result.incomplete_index or incomplete
            if call.label_truncated:
                edge.resolution = "truncated_label"
            elif call.dynamic:
                edge.resolution = "dynamic_or_attribute"
            elif len(matches) > 1:
                edge.resolution = "ambiguous_declaration"
            elif len(matches) == 1:
                target_file, target_symbol = matches[0]
                target = node(target_file, target_symbol)
                if target.id in visited:
                    edge.target = target.id
                    edge.resolution = resolution
                elif depth >= max_depth or len(visited) == MAX_NODES:
                    edge.resolution = "expansion_limit"
                    result.truncated = True
                else:
                    edge.target = target.id
                    edge.resolution = resolution
                    visited.add(target.id)
                    result.nodes.append(target)
                    pending.append((target_file, target_symbol, depth + 1))
            else:
                edge.resolution = resolution
            result.edges.append(edge)
    return result
