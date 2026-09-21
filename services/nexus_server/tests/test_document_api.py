import asyncio

import pytest

from app.documents.embeddings import LocalEmbeddingProvider
from tests.test_run_api import api_client, wait_for_terminal_run


@pytest.fixture(autouse=True)
def hash_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    # Integration tests exercise deterministic fallback retrieval, not model loading.
    monkeypatch.setattr(LocalEmbeddingProvider, "_load", lambda self: None)


async def test_documents_share_mission_workspace_and_citations() -> None:
    async with api_client() as client:
        response = await client.post(
            "/api/v1/documents",
            files={
                "file": (
                    "resume.txt",
                    b"Flutter project: Nexus assistant.",
                    "text/plain",
                ),
            },
        )
        assert response.status_code == 202
        doc_id = response.json()["id"]
        for _ in range(100):
            document = (await client.get(f"/api/v1/documents/{doc_id}")).json()
            if document["status"] == "indexed":
                break
            await asyncio.sleep(0.01)
        assert document["status"] == "indexed"
        assert (await client.get("/api/v1/documents")).json()[0]["id"] == doc_id
        created = await client.post(
            "/api/v1/runs", json={"goal": "Search documents for Flutter"}
        )
        run = await wait_for_terminal_run(client, created.json()["id"])
        assert run["status"] == "completed"
        assert "Nexus assistant" in run["final_response"]
        assert doc_id in run["final_response"] and "chunk " in run["final_response"]
        assert (await client.get("/api/v1/tasks")).json() == []


async def test_legacy_workspace_remains_explicit_and_isolated() -> None:
    async with api_client() as client:
        uploaded = await client.post(
            "/api/v1/documents?user_id=default",
            files={
                "file": ("legacy.txt", b"Legacy document", "text/plain"),
            },
        )
        doc_id = uploaded.json()["id"]
        assert (await client.get("/api/v1/documents")).json() == []
        assert len((await client.get("/api/v1/documents?user_id=default")).json()) == 1
        assert (await client.get(f"/api/v1/documents/{doc_id}")).status_code == 404
        assert (await client.delete(f"/api/v1/documents/{doc_id}")).status_code == 404
        assert (
            await client.delete(f"/api/v1/documents/{doc_id}?user_id=default")
        ).status_code == 204


async def test_document_upload_limits_and_workspace_validation() -> None:
    async with api_client() as client:
        assert (
            await client.post(
                "/api/v1/documents",
                files={
                    "file": ("large.txt", b"x" * (20 * 1024 * 1024 + 1), "text/plain"),
                },
            )
        ).status_code == 413
        assert (
            await client.post(
                "/api/v1/documents",
                files={
                    "file": ("bad.exe", b"not supported", "application/x-msdownload"),
                },
            )
        ).status_code == 415
        assert (await client.get("/api/v1/documents?user_id=")).status_code == 422
