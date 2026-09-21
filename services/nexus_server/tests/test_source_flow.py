import pytest

from app.code.flow import source_flow
from tests.test_code import archive, index
from tests.test_run_api import api_client, wait_for_terminal_run


def test_branching_candidates_cycles_and_unresolved_calls() -> None:
    snapshot = index(
        {
            "app.py": (
                "def login():\n    verify()\n    save()\n    client.send()\n"
                "def verify():\n    login()\n"
                "def save():\n    missing()\n"
            )
        }
    )
    flow = source_flow(snapshot, "app.py", "login")
    assert [node.name for node in flow.nodes] == ["login", "verify", "save"]
    assert [edge.resolution for edge in flow.edges] == [
        "same_file_name_candidate",
        "same_file_name_candidate",
        "dynamic_or_attribute",
        "same_file_name_candidate",
        "unresolved",
    ]
    assert flow.edges[3].target == flow.entry
    assert flow.edges[0].line == 2
    assert len(flow.nodes[0].sha256) == 64
    assert not flow.truncated and not flow.incomplete_index
    assert "NOT verified" in flow.semantics
    assert flow == source_flow(snapshot, "app.py", "login")


def test_ambiguous_declarations_are_not_followed() -> None:
    flow = source_flow(
        index(
            {
                "app.py": (
                    "def login(): helper()\ndef helper(): pass\ndef helper(): pass"
                )
            }
        ),
        "app.py",
        "login",
    )
    assert len(flow.nodes) == 1
    assert flow.edges[0].resolution == "ambiguous_declaration"
    assert flow.edges[0].target is None


def test_depth_node_and_edge_budgets() -> None:
    snapshot = index({"app.py": "def login(): helper()\ndef helper(): login()"})
    flow = source_flow(snapshot, "app.py", "login", 0)
    assert flow.truncated and len(flow.nodes) == 1
    assert flow.edges[0].resolution == "expansion_limit"
    many = index({"app.py": "def login():\n" + "    f()\n" * 101})
    assert len(source_flow(many, "app.py", "login").edges) == 100
    assert source_flow(many, "app.py", "login").truncated
    fan = index(
        {
            "app.py": "def login():\n"
            + "".join(f"    f{i}()\n" for i in range(30))
            + "".join(f"def f{i}(): pass\n" for i in range(30))
        }
    )
    graph = source_flow(fan, "app.py", "login")
    assert len(graph.nodes) == 25 and graph.truncated
    assert all(
        edge.target is None or edge.target in {n.id for n in graph.nodes}
        for edge in graph.edges
    )


def test_old_indexes_and_dynamic_calls_stay_explicit() -> None:
    snapshot = index({"app.py": "def login(): callbacks[0]()"})
    assert source_flow(snapshot, "app.py", "login").edges[0].target is None
    snapshot.files[0].calls = []
    snapshot.files[0].calls_indexed = False
    result = source_flow(snapshot, "app.py", "login")
    assert result.incomplete_index and not result.edges


@pytest.mark.parametrize("symbol", ["missing", "App", "duplicate"])
def test_entries_must_be_unique_functions(symbol: str) -> None:
    snapshot = index(
        {"app.py": "class App: pass\ndef duplicate(): pass\ndef duplicate(): pass"}
    )
    with pytest.raises(ValueError):
        source_flow(snapshot, "app.py", symbol)


async def test_flow_api_mission_and_workspace_isolation() -> None:
    async with api_client() as client:
        upload = await client.post(
            "/api/v1/repositories?name=Login",
            files={
                "file": (
                    "login.zip",
                    archive({"app.py": "def login(): verify()\ndef verify(): pass"}),
                    "application/zip",
                ),
            },
        )
        repo_id = upload.json()["id"]
        url = f"/api/v1/repositories/{repo_id}/flow"
        args = {"path": "app.py", "symbol": "login"}
        response = await client.get(url, params=args)
        assert response.status_code == 200
        assert response.json()["nodes"][1]["name"] == "verify"
        assert (
            await client.get(url, params={**args, "user_id": "other"})
        ).status_code == 404
        assert (
            await client.get(url, params={**args, "path": "../../.env"})
        ).status_code == 404
        assert (
            await client.get(url, params={**args, "symbol": "missing"})
        ).status_code == 422
        assert (
            await client.get(url, params={**args, "max_depth": 6})
        ).status_code == 422
        created = await client.post(
            "/api/v1/runs",
            json={
                "goal": f"Inspect flow in {repo_id} at app.py::login",
            },
        )
        run = await wait_for_terminal_run(client, created.json()["id"])
        assert run["status"] == "completed"
        assert "possible declaration app.py:2" in run["final_response"]
        assert "NOT verified" in run["final_response"]
        assert len(run["context"]["observations"][0]["output"]["nodes"]) == 2
        assert (await client.get("/api/v1/tasks")).json() == []
