"""Resolve declaration candidates from explicit module-level import syntax."""

from pathlib import PurePosixPath

from app.code.models import CodeSymbol, SourceFile

Candidate = tuple[SourceFile, CodeSymbol]


def partial(source: SourceFile) -> bool:
    return (
        not source.calls_indexed
        or not source.bindings_indexed
        or source.parse_error
        or source.index_truncated
        or source.calls_truncated
        or source.bindings_truncated
    )


def flow_sources(files: list[SourceFile], root: str) -> dict[str, SourceFile]:
    if root and (
        len(root) > 300
        or "\\" in root
        or ":" in root
        or any(part in {"", ".", ".."} for part in root.split("/"))
        or any(ord(char) < 32 or ord(char) == 127 for char in root)
    ):
        raise ValueError("Source root must be a relative snapshot directory.")
    prefix = root + "/" if root else ""
    sources = {file.path: file for file in files if file.path.startswith(prefix)}
    if root and not sources:
        raise ValueError("Source root is not present in the snapshot.")
    return sources


def declaration_candidates(
    source: SourceFile,
    callee: str,
    files: dict[str, SourceFile],
    root: str,
) -> tuple[list[Candidate], str, bool]:
    local = [
        (source, symbol)
        for symbol in source.symbols
        if symbol.kind == "function" and symbol.name == callee and "." not in callee
    ]
    matches = []
    for binding in source.bindings:
        if binding.scope:
            continue  # Function/class-local imports are not followed.
        if binding.member is not None:
            if binding.member != "*" and callee == binding.binding:
                matches.append((binding, binding.member))
        elif callee.startswith(binding.binding + "."):
            member = callee[len(binding.binding) + 1 :]
            if "." not in member:
                matches.append((binding, member))
    if not matches:
        return (
            local,
            (
                "same_file_name_candidate"
                if local
                else "dynamic_or_attribute"
                if "." in callee
                else "unresolved"
            ),
            False,
        )
    if len(matches) != 1 or local:
        return [], "ambiguous_binding", False
    binding, member = matches[0]
    module = binding.module
    levels = len(module) - len(module.lstrip("."))
    tail = module[levels:]
    prefix = root + "/" if root else ""
    parents = PurePosixPath(source.path[len(prefix) :]).parent.parts
    if not tail or (levels and (not parents or levels > len(parents))):
        return [], "unresolved_relative_import", False
    parts = (
        [*parents[: len(parents) - levels + 1], *tail.split(".")]
        if levels
        else tail.split(".")
    )
    stem = prefix + "/".join(parts)
    targets = [
        files[path]
        for path in (stem + ".py", stem + "/__init__.py")
        if path in files and files[path].language == "python"
    ]
    if len(targets) != 1:
        return [], "ambiguous_module" if targets else "unresolved_import", False
    target = targets[0]
    symbols = [
        item
        for item in target.symbols
        if item.kind == "function" and item.name == member
    ]
    return (
        [(target, item) for item in symbols],
        ("import_name_candidate" if symbols else "unresolved_imported_member"),
        partial(target),
    )
