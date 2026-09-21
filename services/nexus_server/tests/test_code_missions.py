import pytest

from tests.test_code import archive
from tests.test_run_api import api_client, wait_for_terminal_run


@pytest.mark.parametrize(
    "goal,tool,expected",
    [
        ("Call sites in {id}", "call_sites", "[login] verify"),
        ("Dependencies in {id} under src", "dependency_graph", "src/auth.py"),
    ],
)
async def test_source_inspection_missions_use_uploaded_evidence(
    goal: str,
    tool: str,
    expected: str,
) -> None:
    async with api_client() as client:
        upload = await client.post(
            "/api/v1/repositories?name=Flow",
            files={
                "file": (
                    "flow.zip",
                    archive(
                        {
                            "src/app.py": "import auth\ndef login():\n    verify()",
                            "src/auth.py": "pass",
                        }
                    ),
                    "application/zip",
                ),
            },
        )
        repo_id = upload.json()["id"]
        response = await client.post(
            "/api/v1/runs", json={"goal": goal.format(id=repo_id)}
        )
        run = await wait_for_terminal_run(client, response.json()["id"])
        assert run["status"] == "completed"
        assert expected in run["final_response"]
        assert repo_id in run["final_response"]
        assert "src/app.py:" in run["final_response"]
        assert "not " in run["final_response"]
        assert run["context"]["observations"][0]["tool"] == tool
        assert (await client.get("/api/v1/tasks")).json() == []


async def test_call_mission_discloses_bounded_summary() -> None:
    async with api_client() as client:
        upload = await client.post(
            "/api/v1/repositories?name=Many",
            files={
                "file": (
                    "many.zip",
                    archive({"app.py": "verify()\n" * 21}),
                    "application/zip",
                ),
            },
        )
        response = await client.post(
            "/api/v1/runs",
            json={
                "goal": f"Call sites in {upload.json()['id']}",
            },
        )
        run = await wait_for_terminal_run(client, response.json()["id"])
        assert run["status"] == "completed"
        assert "Results bounded" in run["final_response"]
        assert "app.py:21 " not in run["final_response"]
