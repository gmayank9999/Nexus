"""Exercise mock voice transport and explicitly submit its goal to a local API."""

import argparse
import asyncio
import json

import httpx
from websockets.asyncio.client import connect


async def verify(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:
        status = await client.get("/api/v1/voice/status")
        status.raise_for_status()
        if not status.json()["enabled"] or status.json()["provider"] != "mock":
            raise RuntimeError(
                "This check requires enabled mock voice; no real audio is used."
            )
        ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
        async with asyncio.timeout(20):
            async with connect(f"{ws_base}/ws/voice") as socket:
                assert json.loads(await socket.recv())["type"] == "ready"
                await socket.send(b"\0\0" * 4000)
                await socket.send(json.dumps({"type": "finish"}))
                assert json.loads(await socket.recv())["type"] == "transcribing"
                transcript = json.loads(await socket.recv())
                assert transcript["type"] == "transcript"
                assert transcript["is_mock"] is True
        # Explicit submission, just like reviewing and pressing Start in Flutter.
        response = await client.post(
            "/api/v1/runs",
            json={
                "goal": transcript["text"],
                "user_id": "voice-smoke",
            },
        )
        response.raise_for_status()
        run_id = response.json()["id"]
        async with asyncio.timeout(20):
            while True:
                response = await client.get(f"/api/v1/runs/{run_id}")
                response.raise_for_status()
                run = response.json()
                if run["status"] in {"completed", "failed", "cancelled"}:
                    break
                await asyncio.sleep(0.1)
        assert run["status"] == "completed", run["status"]
        print(
            json.dumps({"run_id": run_id, "status": run["status"], "mock_voice": True})
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    asyncio.run(verify(args.base_url.rstrip("/")))
