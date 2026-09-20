import asyncio
import io
import stat
import threading
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.routes import code as code_routes
from app.code.indexer import RepositoryImportError, index_archive
from app.code.repository import InMemoryCodeRepository, SqlCodeRepository
from app.storage.tables import initialize_schema
from tests.test_run_api import api_client


def archive(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, content in files.items():
            zipped.writestr(name, content)
    return buffer.getvalue()


def index(files: dict[str, str]):
    return index_archive(archive(files), user_id="local", name="Example")


def test_python_symbols_imports_and_no_execution() -> None:
    snapshot = index(
        {
            "app.py": (
                "import os\nfrom .auth import login\n"
                "raise RuntimeError('must never execute')\n"
                "class App:\n    async def login(self):\n        return 1\n"
            )
        }
    )
    source = snapshot.files[0]
    assert [(s.name, s.line, s.end_line) for s in source.symbols] == [
        ("App", 4, 6),
        ("App.login", 5, 6),
    ]
    assert [item.module for item in source.imports] == ["os", ".auth"]
    assert len(source.sha256) == 64


def test_syntax_errors_and_other_languages_remain_searchable() -> None:
    snapshot = index({"broken.py": "def ???", "app.dart": "void main() {}"})
    assert snapshot.files[0].language == "dart"
    assert not snapshot.files[0].symbols
    assert snapshot.files[1].parse_error


def test_excludes_hidden_vendor_binary_and_unsupported_files() -> None:
    snapshot = index(
        {
            "app.py": "pass",
            ".private/key.py": "secret",
            "node_modules/x.js": "x",
            "data.txt": "x",
            "binary.py": "\0",
            "build/a.py": "pass",
        }
    )
    assert [source.path for source in snapshot.files] == ["app.py"]
    assert snapshot.skipped_files == 5


@pytest.mark.parametrize(
    "path",
    ["../evil.py", "/absolute.py", "a/../b.py", "C:/evil.py", "a\\b.py", "a//b.py"],
)
def test_unsafe_paths_rejected(path: str) -> None:
    # zipfile normalizes backslashes when writing on Windows; patch both ZIP
    # headers to exercise an actual hostile archive from another platform.
    normalized = path.replace("\\", "/")
    content = archive({normalized: "pass"}).replace(normalized.encode(), path.encode())
    with pytest.raises(RepositoryImportError, match="unsafe"):
        index_archive(content, user_id="local", name="Unsafe")


def test_symlinks_and_case_collisions_rejected() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        link = zipfile.ZipInfo("link.py")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        zipped.writestr(link, "../../secret")
    with pytest.raises(RepositoryImportError, match="unsafe"):
        index_archive(buffer.getvalue(), user_id="local", name="Link")
    with pytest.raises(RepositoryImportError, match="duplicate"):
        index({"app.py": "pass", "APP.py": "pass"})


@pytest.mark.parametrize(
    "files,message",
    [
        ({"a.py": "x" * (256 * 1024 + 1)}, "256 KiB"),
        ({f"a{i}.py": "pass" for i in range(201)}, "200 source"),
        ({"ignored.bin": "x" * (10 * 1024 * 1024 + 1)}, "10 MiB"),
        ({f"d{i}/": "" for i in range(1001)}, "1000 entries"),
        ({"readme.md": "No source"}, "no supported"),
    ],
)
def test_archive_budgets(files: dict[str, str], message: str) -> None:
    with pytest.raises(RepositoryImportError, match=message):
        index(files)


def test_malformed_and_large_uploads_rejected() -> None:
    for content in [b"not a zip", b"x" * (5 * 1024 * 1024 + 1)]:
        with pytest.raises(RepositoryImportError):
            index_archive(content, user_id="local", name="Invalid")


async def test_repository_api_source_locations_and_workspace_isolation() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/repositories?name=Sample",
            files={
                "file": (
                    "sample.zip",
                    archive({"app.py": "def login():\n    return 'ok'\n"}),
                    "application/zip",
                ),
            },
        )
        assert response.status_code == 201
        repository_id = response.json()["id"]
        assert response.json()["file_count"] == 1
        listed = await client.get("/api/v1/repositories")
        assert listed.json()[0]["id"] == repository_id
        assert "content" not in str(listed.json())
        files = await client.get(f"/api/v1/repositories/{repository_id}/files")
        assert files.json()["files"][0]["symbols"][0]["name"] == "login"
        assert "content" not in files.json()["files"][0]
        search = await client.get(
            f"/api/v1/repositories/{repository_id}/search?query=LOGIN"
        )
        assert search.json()["matches"][0]["line"] == 1
        read = await client.get(
            f"/api/v1/repositories/{repository_id}/file?path=app.py&start_line=2"
        )
        assert read.json()["content"] == "    return 'ok'"
        for endpoint in ["files", "file?path=app.py", "search?query=login"]:
            separator = "&" if "?" in endpoint else "?"
            denied = await client.get(
                f"/api/v1/repositories/{repository_id}/{endpoint}{separator}user_id=other"
            )
            assert denied.status_code == 404


async def test_search_is_bounded_and_rejects_blank_query() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/repositories?name=Many",
            files={
                "file": (
                    "sample.zip",
                    archive({"app.py": "# login\n" * 30}),
                    "application/zip",
                ),
            },
        )
        prefix = f"/api/v1/repositories/{response.json()['id']}"
        result = (await client.get(f"{prefix}/search?query=login")).json()
        assert len(result["matches"]) == 20 and result["truncated"]
        assert (await client.get(f"{prefix}/search?query=%20")).status_code == 422


async def test_snapshot_survives_database_reopen(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'code.db'}"
    database = create_async_engine(url)
    snapshot = index({"app.py": "def login(): pass"})
    try:
        await initialize_schema(database)
        await SqlCodeRepository(database).create(snapshot)
    finally:
        await database.dispose()
    reopened = create_async_engine(url)
    try:
        repository = SqlCodeRepository(reopened)
        assert await repository.get(snapshot.id, "local") == snapshot
        assert await repository.get(snapshot.id, "other") is None
        assert (await repository.list_for_user("local"))[0].file_count == 1
    finally:
        await reopened.dispose()


async def test_cancelled_request_holds_slot_until_worker_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    real_index = index_archive

    def slow_index(*args, **kwargs):
        entered.set()
        assert release.wait(timeout=5)
        return real_index(*args, **kwargs)

    monkeypatch.setattr(code_routes, "index_archive", slow_index)
    resources = SimpleNamespace(
        code_import_slots=asyncio.Semaphore(1), code_repository=InMemoryCodeRepository()
    )
    upload = UploadFile(file=io.BytesIO(archive({"app.py": "pass"})))
    task = asyncio.create_task(code_routes.import_repository(upload, resources, "Test"))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        with pytest.raises(HTTPException) as busy:
            await code_routes.import_repository(upload, resources, "Busy")
        assert busy.value.status_code == 503
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert resources.code_import_slots.locked()
    finally:
        release.set()
        async with asyncio.timeout(3):
            await resources.code_import_slots.acquire()
        resources.code_import_slots.release()
        await upload.close()
    assert await resources.code_repository.list_for_user("local") == []
