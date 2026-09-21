import pytest

from app.code.flow import source_flow
from app.code.models import SourceFile
from tests.test_code import archive, index
from tests.test_run_api import api_client, wait_for_terminal_run


@pytest.mark.parametrize(
    "statement,call",
    [
        ("from auth import verify", "verify"),
        ("from auth import verify as check", "check"),
        ("import auth", "auth.verify"),
        ("import auth as a", "a.verify"),
    ],
)
def test_explicit_imports_link_to_cited_candidates(statement: str, call: str) -> None:
    snapshot = index(
        {
            "app.py": f"{statement}\ndef login(): {call}()",
            "auth.py": "def verify(): pass",
        }
    )
    graph = source_flow(snapshot, "app.py", "login")
    assert graph.nodes[1].path == "auth.py"
    assert graph.nodes[1].sha256 == snapshot.files[1].sha256
    assert graph.edges[0].resolution == "import_name_candidate"
    assert not graph.incomplete_index


def test_relative_dotted_imports_and_cross_file_cycles() -> None:
    snapshot = index(
        {
            "pkg/app.py": "from .auth import verify\ndef login(): verify()",
            "pkg/auth.py": "import pkg.app\ndef verify(): pkg.app.login()",
        }
    )
    graph = source_flow(snapshot, "pkg/app.py", "login")
    assert len(graph.nodes) == 2 and len(graph.edges) == 2
    assert graph.edges[1].target == graph.entry


def test_source_root_is_explicit_and_validated() -> None:
    snapshot = index(
        {
            "src/app.py": "import auth\ndef login(): auth.verify()",
            "src/auth.py": "def verify(): pass",
        }
    )
    assert source_flow(snapshot, "src/app.py", "login").edges[0].target is None
    assert (
        len(source_flow(snapshot, "src/app.py", "login", source_root="src").nodes) == 2
    )
    with pytest.raises(ValueError):
        source_flow(snapshot, "src/app.py", "login", source_root="../src")


@pytest.mark.parametrize(
    "files,reason",
    [
        (
            {
                "app.py": (
                    "from auth import verify\ndef verify(): pass\ndef login(): verify()"
                ),
                "auth.py": "def verify(): pass",
            },
            "ambiguous_binding",
        ),
        (
            {
                "app.py": "import auth\ndef login(): auth.verify()",
                "auth.py": "def verify(): pass",
                "auth/__init__.py": "def verify(): pass",
            },
            "ambiguous_module",
        ),
        (
            {
                "app.py": "from auth import verify\ndef login(): verify()",
                "auth.py": "def verify(): pass\ndef verify(): pass",
            },
            "ambiguous_declaration",
        ),
        (
            {
                "app.py": "from auth import *\ndef login(): verify()",
                "auth.py": "def verify(): pass",
            },
            "unresolved",
        ),
        (
            {
                "app.py": "def login():\n    import auth\n    auth.verify()",
                "auth.py": "def verify(): pass",
            },
            "dynamic_or_attribute",
        ),
        (
            {
                "app.py": "from . import auth\ndef login(): auth.verify()",
                "auth.py": "def verify(): pass",
            },
            "dynamic_or_attribute",
        ),
    ],
)
def test_ambiguous_and_unsupported_bindings_stay_unresolved(
    files: dict[str, str], reason: str
) -> None:
    graph = source_flow(index(files), "app.py", "login")
    assert len(graph.nodes) == 1 and graph.edges[0].target is None
    assert graph.edges[0].resolution == reason


def test_legacy_binding_index_and_bad_target_are_incomplete() -> None:
    snapshot = index(
        {
            "app.py": "from auth import verify\ndef login(): verify()",
            "auth.py": "def ??",
        }
    )
    assert source_flow(snapshot, "app.py", "login").incomplete_index
    legacy = snapshot.files[0].model_dump(
        exclude={"bindings", "bindings_indexed", "bindings_truncated"}
    )
    snapshot.files[0] = SourceFile.model_validate(legacy)
    graph = source_flow(snapshot, "app.py", "login")
    assert graph.incomplete_index and graph.edges[0].target is None


def test_binding_budget_does_not_expand_unbounded_member_lists() -> None:
    snapshot = index(
        {"app.py": "from auth import " + ",".join(f"f{i}" for i in range(501))}
    )
    assert len(snapshot.files[0].bindings) == 500
    assert snapshot.files[0].bindings_truncated


async def test_rooted_cross_file_mission_and_api() -> None:
    async with api_client() as client:
        upload = await client.post(
            "/api/v1/repositories?name=Cross",
            files={
                "file": (
                    "cross.zip",
                    archive(
                        {
                            "src/app.py": "import auth\ndef login(): auth.verify()",
                            "src/auth.py": "def verify(): pass",
                        }
                    ),
                    "application/zip",
                ),
            },
        )
        repo_id = upload.json()["id"]
        response = await client.get(
            f"/api/v1/repositories/{repo_id}/flow",
            params={
                "path": "src/app.py",
                "symbol": "login",
                "source_root": "src",
            },
        )
        assert response.status_code == 200 and len(response.json()["nodes"]) == 2
        created = await client.post(
            "/api/v1/runs",
            json={
                "goal": f"Inspect flow in {repo_id} at src/app.py::login under src",
            },
        )
        run = await wait_for_terminal_run(client, created.json()["id"])
        assert run["status"] == "completed"
        assert "possible declaration src/auth.py:1" in run["final_response"]
        assert "NOT verified" in run["final_response"]
