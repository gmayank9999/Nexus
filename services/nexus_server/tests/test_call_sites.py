from app.code.calls import call_sites
from app.code.models import SourceFile
from tests.test_code import archive, index
from tests.test_code_tools import context, tools_for
from tests.test_run_api import api_client


def test_calls_are_lexical_evidence_not_executed_or_resolved() -> None:
    snapshot = index(
        {
            "app.py": (
                "raise RuntimeError('never execute')\n"
                "@decorate()\n"
                "def login(value=default()):\n"
                "    verify(value)\n"
                "    client.save(value)\n"
                "    factory()()\n"
                "    callbacks[0]()\n"
            )
        }
    )
    result = call_sites(snapshot)
    assert not result.incomplete_index
    assert [call.callee for call in result.calls] == [
        "RuntimeError",
        "decorate",
        "default",
        "verify",
        "client.save",
        "<dynamic expression>",
        "factory",
        "<dynamic expression>",
    ]
    assert result.calls[0].scope == "<module>"
    assert result.calls[3].scope == "login"
    assert result.calls[3].line == 4 and result.calls[3].column == 4
    assert result.calls[-1].dynamic
    assert all(len(call.sha256) == 64 for call in result.calls)
    assert "not resolved" in result.semantics


def test_nested_async_scopes_and_bounded_labels() -> None:
    snapshot = index(
        {
            "app.py": (
                "class App:\n"
                "    async def run(self):\n"
                "        await client.fetch()\n"
                "        def nested():\n"
                "            " + "x" * 301 + "()\n"
            )
        }
    )
    calls = call_sites(snapshot).calls
    assert calls[0].scope == "App.run"
    assert calls[1].scope == "App.run.nested"
    assert len(calls[1].callee) == 300 and calls[1].label_truncated


def test_call_budgets_and_partial_indexes() -> None:
    result = call_sites(index({"app.py": "f()\n" * 501}))
    assert len(result.calls) == 500 and result.truncated and result.incomplete_index
    exact = call_sites(index({"app.py": "f()\n" * 500}))
    assert not exact.truncated and not exact.incomplete_index
    cross_file = call_sites(index({"a.py": "f()\n" * 300, "b.py": "g()\n" * 300}))
    assert len(cross_file.calls) == 500 and cross_file.truncated
    assert call_sites(index({"broken.py": "def ?", "app.js": "f()"})).incomplete_index


def test_legacy_snapshots_are_not_mistaken_for_complete_empty_indexes() -> None:
    snapshot = index({"app.py": "f()"})
    legacy = snapshot.files[0].model_dump(
        exclude={"calls", "calls_indexed", "calls_truncated"}
    )
    snapshot.files = [SourceFile.model_validate(legacy)]
    result = call_sites(snapshot)
    assert not result.calls and result.incomplete_index


async def test_call_tool_uses_indexed_evidence() -> None:
    tools, repo_id = await tools_for({"app.py": "def login():\n    verify()"})
    result = await tools.execute("call_sites", {"repository_id": repo_id}, context())
    assert result.output["calls"][0]["scope"] == "login"
    assert result.output["calls"][0]["callee"] == "verify"


async def test_call_api_is_workspace_scoped() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/repositories?name=Calls",
            files={
                "file": (
                    "calls.zip",
                    archive({"app.py": "login()"}),
                    "application/zip",
                ),
            },
        )
        assert response.status_code == 201
        url = f"/api/v1/repositories/{response.json()['id']}/calls"
        result = await client.get(url)
        assert result.status_code == 200
        assert result.json()["calls"][0]["callee"] == "login"
        assert (await client.get(url, params={"user_id": "other"})).status_code == 404
