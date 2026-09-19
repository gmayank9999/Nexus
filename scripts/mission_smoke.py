"""Verify an existing mission and WebSocket replay against a running server."""

import argparse
import asyncio
import json

import httpx
from websockets.asyncio.client import connect


async def verify(base_url: str, run_id: str, user_id: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:
        response = await client.get(f"/api/v1/runs/{run_id}")
        response.raise_for_status()
        run = response.json()
        assert run["status"] == "completed", run["status"]
        assert run["current_step"] == 2
        params = {"user_id": user_id, "run_id": run_id}
        tasks = await client.get("/api/v1/tasks", params=params)
        artifacts = await client.get("/api/v1/artifacts", params=params)
        tasks.raise_for_status()
        artifacts.raise_for_status()
        assert len(tasks.json()) == 1
        assert len(artifacts.json()) == 1
        assert artifacts.json()[0]["type"] == "study_guide"

        cursor = 7
        ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
        sequences = []
        async with asyncio.timeout(15):
            async with connect(
                f"{ws_base}/ws/runs/{run_id}?last_seen_sequence={cursor}"
            ) as websocket:
                async for message in websocket:
                    event = json.loads(message)
                    sequences.append(event["sequence"])
                    if event["type"] == "run_completed":
                        break
        assert sequences == list(range(cursor + 1, len(run["trace"]) + 1))
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "status": run["status"],
                    "tasks": len(tasks.json()),
                    "artifacts": len(artifacts.json()),
                    "websocket_replayed": len(sequences),
                }
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--user-id", default="local")
    args = parser.parse_args()
    asyncio.run(verify(args.base_url.rstrip("/"), args.run_id, args.user_id))
