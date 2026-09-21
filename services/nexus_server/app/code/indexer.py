"""Bounded ZIP inspection. Never extract, import, compile, or execute source."""

import ast
import hashlib
import io
import re
import stat
import zipfile
import zlib
from pathlib import PurePosixPath

from app.code.models import (
    CodeCall,
    CodeImport,
    CodeSymbol,
    ImportBinding,
    RepositorySnapshot,
    SourceFile,
)

MAX_ARCHIVE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 10 * 1024 * 1024
MAX_FILE_BYTES = 256 * 1024
MAX_ENTRIES = 1000
MAX_SOURCE_FILES = 200
MAX_INDEX_ITEMS = 1000
LANGUAGES = {
    ".py": "python",
    ".dart": "dart",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}
EXCLUDED = {"node_modules", "vendor", "build", "dist", "__pycache__", "coverage"}


class RepositoryImportError(ValueError):
    pass


def index_archive(content: bytes, *, user_id: str, name: str) -> RepositorySnapshot:
    if len(content) > MAX_ARCHIVE_BYTES:
        raise RepositoryImportError("Archive exceeds the 5 MiB limit.")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ENTRIES:
                raise RepositoryImportError("Archive exceeds 1000 entries.")
            if sum(entry.file_size for entry in entries) > MAX_TOTAL_BYTES:
                raise RepositoryImportError("Archive exceeds 10 MiB uncompressed.")
            files: list[SourceFile] = []
            skipped = 0
            seen: set[str] = set()
            for entry in entries:
                path = _safe_path(entry)
                key = path.casefold()
                if key in seen:
                    raise RepositoryImportError("Archive contains duplicate paths.")
                seen.add(key)
                if entry.is_dir():
                    continue
                parts = PurePosixPath(path).parts
                suffix = PurePosixPath(path).suffix.lower()
                if (
                    any(
                        part.startswith(".") or part.casefold() in EXCLUDED
                        for part in parts
                    )
                    or suffix not in LANGUAGES
                ):
                    skipped += 1
                    continue
                if entry.file_size > MAX_FILE_BYTES:
                    raise RepositoryImportError("A source file exceeds 256 KiB.")
                if len(files) >= MAX_SOURCE_FILES:
                    raise RepositoryImportError("Archive exceeds 200 source files.")
                with archive.open(entry) as stream:
                    raw = stream.read(MAX_FILE_BYTES + 1)
                if len(raw) > MAX_FILE_BYTES:
                    raise RepositoryImportError("A source file exceeds 256 KiB.")
                try:
                    text = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    skipped += 1
                    continue
                if "\0" in text:
                    skipped += 1
                    continue
                source = SourceFile(
                    path=path,
                    language=LANGUAGES[suffix],
                    content=text,
                    sha256=hashlib.sha256(raw).hexdigest(),
                )
                if source.language == "python":
                    _index_python(source)
                files.append(source)
            if not files:
                raise RepositoryImportError(
                    "Archive contains no supported UTF-8 source files."
                )
    except (
        zipfile.BadZipFile,
        RuntimeError,
        NotImplementedError,
        EOFError,
        zlib.error,
    ) as error:
        raise RepositoryImportError(
            "Archive is invalid, encrypted, or unsupported."
        ) from error
    return RepositorySnapshot(
        user_id=user_id,
        name=name,
        archive_sha256=hashlib.sha256(content).hexdigest(),
        files=sorted(files, key=lambda file: file.path),
        skipped_files=skipped,
    )


def _safe_path(entry: zipfile.ZipInfo) -> str:
    name = entry.filename.rstrip("/")
    parts = name.split("/")
    mode = entry.external_attr >> 16
    if (
        not name
        or entry.orig_filename != entry.filename
        or len(name) > 300
        or "\\" in name
        or ":" in name
        or any(part in {"", ".", ".."} for part in parts)
        or re.search(r"[\x00-\x1f\x7f]", name)
        or stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}
        or entry.flag_bits & 1
    ):
        raise RepositoryImportError("Archive contains an unsafe path or entry.")
    if entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
        raise RepositoryImportError(
            "Only stored or deflated ZIP entries are supported."
        )
    return name


def _index_python(source: SourceFile) -> None:
    try:
        tree = ast.parse(source.content)
    except (SyntaxError, ValueError, RecursionError):
        source.parse_error = True
        return
    source.calls_indexed = True
    source.bindings_indexed = True
    # Iterative traversal avoids recursion on deeply nested uploaded syntax.
    pending: list[tuple[ast.AST, str]] = [(tree, "")]
    while pending:
        node, scope = pending.pop()
        next_scope = scope
        if isinstance(node, ast.Import | ast.ImportFrom):
            remaining_bindings = 500 - len(source.bindings)
            for alias in node.names[:remaining_bindings]:
                source.bindings.append(
                    ImportBinding(
                        module=(
                            alias.name
                            if isinstance(node, ast.Import)
                            else "." * node.level + (node.module or "")
                        ),
                        binding=alias.asname or alias.name,
                        member=alias.name if isinstance(node, ast.ImportFrom) else None,
                        scope=scope,
                        line=node.lineno,
                    )
                )
            if len(node.names) > remaining_bindings:
                source.bindings_truncated = True
        if isinstance(node, ast.Call):
            if len(source.calls) < 500:
                callee, dynamic, truncated = _callee_label(node.func)
                source.calls.append(
                    CodeCall(
                        scope=scope[:300] or "<module>",
                        callee=callee,
                        line=node.lineno,
                        column=node.col_offset,
                        dynamic=dynamic,
                        label_truncated=truncated or len(scope) > 300,
                    )
                )
            else:
                source.calls_truncated = True
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            next_scope = f"{scope}.{node.name}" if scope else node.name
            source.symbols.append(
                CodeSymbol(
                    name=next_scope,
                    kind="class" if isinstance(node, ast.ClassDef) else "function",
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                )
            )
        elif isinstance(node, ast.Import):
            remaining = MAX_INDEX_ITEMS - len(source.symbols) - len(source.imports)
            source.imports.extend(
                CodeImport(module=alias.name, line=node.lineno)
                for alias in node.names[:remaining]
            )
        elif isinstance(node, ast.ImportFrom):
            source.imports.append(
                CodeImport(
                    module="." * node.level + (node.module or ""), line=node.lineno
                )
            )
        if len(source.symbols) + len(source.imports) >= MAX_INDEX_ITEMS:
            source.imports = source.imports[
                : max(0, MAX_INDEX_ITEMS - len(source.symbols))
            ]
            source.index_truncated = True
            break
        pending.extend(
            (child, next_scope) for child in reversed(list(ast.iter_child_nodes(node)))
        )
    source.symbols.sort(key=lambda item: (item.line, item.name))
    source.imports.sort(key=lambda item: (item.line, item.module))
    source.calls.sort(key=lambda item: (item.line, item.column))


def _callee_label(node: ast.expr) -> tuple[str, bool, bool]:
    """Describe syntax only; never resolve bindings or stringify arguments."""
    parts: list[str] = []
    size = 0
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        size += len(node.attr) + 1
        if size > 300:
            return "<complex attribute call>", True, True
        node = node.value
    if not isinstance(node, ast.Name):
        return "<dynamic expression>", True, False
    parts.append(node.id)
    label = ".".join(reversed(parts))
    return label[:300], False, len(label) > 300
