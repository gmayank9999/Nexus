import time

from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app


def test_websocket_replays_events_after_last_seen_sequence() -> None:
    app = create_app(
        Settings(
            app_env="test",
            nexus_llm_provider="mock",
            database_url="postgresql+asyncpg://nexus:nexus@localhost:5432/nexus",
            redis_url="redis://localhost:6379/15",
        )
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runs",
            json={"goal": "Create a task to test WebSocket replay"},
        )
        run_id = response.json()["id"]
        events = _wait_for_events(client, run_id)
        cursor = 4

        with client.websocket_connect(
            f"/ws/runs/{run_id}?last_seen_sequence={cursor}"
        ) as websocket:
            replay = [websocket.receive_json() for _ in events[cursor:]]

    assert [event["sequence"] for event in replay] == list(
        range(cursor + 1, len(events) + 1)
    )
    assert replay[-1]["type"] == "run_completed"


def _wait_for_events(client: TestClient, run_id: str) -> list[dict[str, object]]:
    for _ in range(100):
        response = client.get(f"/api/v1/runs/{run_id}/events")
        events = response.json()
        if events and events[-1]["type"] == "run_completed":
            return events
        time.sleep(0.01)
    raise AssertionError("Run events did not complete")
