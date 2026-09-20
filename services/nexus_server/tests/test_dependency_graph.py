import pytest

from app.code.graph import dependency_graph
from app.tools.base import ToolError
from tests.test_code import archive, index
from tests.test_code_tools import context, tools_for
from tests.test_run_api import api_client


def test_declared_modules_and_relative_imports() -> None:
    snapshot = index(
        {
            "pkg/__init__.py": "",
            "pkg/auth.py": "import pkg.api",
            "pkg/api.py": (
                "from .auth import login\nfrom . import auth\n"
                "from ..outside import x\nimport external\nfrom pkg import auth"
            ),
        }
    )
    graph = dependency_graph(snapshot)
    edges = [edge for edge in graph.edges if edge.source == "pkg/api.py"]
    assert [edge.target for edge in edges] == [
        "pkg/auth.py",
        None,
        None,
        None,
        "pkg/__init__.py",
    ]
    assert [edge.resolution for edge in edges[1:4]] == [
        "relative_members_unresolved",
        "relative_beyond_root",
        "unresolved",
    ]
    assert edges[0].line == 1 and len(edges[0].source_sha256) == 64
    assert graph == dependency_graph(snapshot)
    assert not graph.truncated and not graph.incomplete_index


def test_source_root_ambiguity_and_nested_relative_import() -> None:
    snapshot = index(
        {
            "src/pkg/sub/api.py": "from ..auth import x\nimport duplicate",
            "src/pkg/auth.py": "pass",
            "src/duplicate.py": "pass",
            "src/duplicate/__init__.py": "pass",
        }
    )
    graph = dependency_graph(snapshot, "src")
    assert graph.edges[0].target == "src/pkg/auth.py"
    assert graph.edges[1].resolution == "ambiguous"
    assert dependency_graph(snapshot).edges[1].resolution == "unresolved"


@pytest.mark.parametrize(
    "root",
    ["../src", "/src", "src/", "src\\pkg", "C:src", "missing", "src\x7f", "x" * 301],
)
def test_invalid_source_roots(root: str) -> None:
    with pytest.raises(ValueError):
        dependency_graph(index({"src/app.py": "pass"}), root)


def test_graph_limits_and_partial_index() -> None:
    graph = dependency_graph(
        index(
            {
                "app.py": "import external\n" * 501,
                "bad.py": "def ???",
                "app.js": "let x = 1",
            }
        )
    )
    assert len(graph.edges) == 500 and graph.truncated and graph.incomplete_index
    exact = dependency_graph(index({"app.py": "import external\n" * 500}))
    assert len(exact.edges) == 500 and not exact.truncated
    long_name = dependency_graph(index({"app.py": "import " + "a" * 301})).edges[0]
    assert len(long_name.module) == 300 and long_name.module_truncated


async def test_graph_tool_and_invalid_root() -> None:
    tools, repo_id = await tools_for({"app.py": "import helper", "helper.py": "pass"})
    result = await tools.execute(
        "dependency_graph", {"repository_id": repo_id}, context()
    )
    assert result.output["edges"][0]["target"] == "helper.py"
    with pytest.raises(ToolError) as error:
        await tools.execute(
            "dependency_graph",
            {"repository_id": repo_id, "source_root": "../"},
            context(),
        )
    assert error.value.code == "INVALID_SOURCE_ROOT"


async def test_graph_api_workspace_and_root_validation() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/repositories?name=Graph",
            files={
                "file": (
                    "graph.zip",
                    archive({"src/app.py": "import helper", "src/helper.py": "pass"}),
                    "application/zip",
                )
            },
        )
        assert response.status_code == 201
        url = f"/api/v1/repositories/{response.json()['id']}/dependencies"
        result = await client.get(url, params={"source_root": "src"})
        assert result.status_code == 200
        assert result.json()["edges"][0]["target"] == "src/helper.py"
        assert (await client.get(url, params={"user_id": "other"})).status_code == 404
        assert (await client.get(url, params={"source_root": "../"})).status_code == 422
