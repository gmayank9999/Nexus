import asyncio
import io
import threading
import wave
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config.settings import Settings
from app.main import create_app
from app.voice.provider import Transcript, VoiceError, WhisperCppProvider, pcm_to_wav


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(
        Settings(
            app_env="test",
            nexus_llm_provider="mock",
            nexus_enable_voice=True,
            nexus_voice_provider="mock",
            nexus_voice_max_seconds=1,
            nexus_voice_max_sessions=1,
        )
    )
    with TestClient(app) as client:
        yield client


def test_voice_transcript_requires_explicit_mission_submission(
    client: TestClient,
) -> None:
    assert client.get("/api/v1/voice/status").json()["enabled"] is True
    with client.websocket_connect("/ws/voice") as ws:
        assert ws.receive_json()["sample_rate"] == 16000
        ws.send_bytes(b"\x00\x01" * 4000)
        ws.send_json({"type": "finish"})
        assert ws.receive_json()["type"] == "transcribing"
        transcript = ws.receive_json()
        assert transcript["type"] == "transcript"
        assert transcript["is_mock"] is True
    assert client.get("/api/v1/runs").json() == []
    response = client.post("/api/v1/runs", json={"goal": transcript["text"]})
    assert response.status_code == 201


@pytest.mark.parametrize(
    "payload,code",
    [
        pytest.param(b"x", "INVALID_AUDIO", id="odd-sample"),
        pytest.param(b"\0" * 65538, "INVALID_AUDIO", id="large-frame"),
        pytest.param(b"\0" * 32002, "AUDIO_LIMIT", id="long-recording"),
    ],
)
def test_invalid_audio_is_rejected(
    client: TestClient, payload: bytes, code: str
) -> None:
    with client.websocket_connect("/ws/voice") as ws:
        ws.receive_json()
        ws.send_bytes(payload)
        assert ws.receive_json()["code"] == code


@pytest.mark.parametrize(
    "message,code",
    [
        ('{"type":"finish"}', "AUDIO_TOO_SHORT"),
        ('{"type":"start_mission"}', "INVALID_MESSAGE"),
        ('["finish"]', "INVALID_MESSAGE"),
        ('{"type":"cancel","goal":"hidden"}', "INVALID_MESSAGE"),
        ("x" * 129, "INVALID_MESSAGE"),
    ],
)
def test_invalid_commands(client: TestClient, message: str, code: str) -> None:
    with client.websocket_connect("/ws/voice") as ws:
        ws.receive_json()
        ws.send_text(message)
        assert ws.receive_json()["code"] == code


def test_disabled_voice_never_opens_a_session(client: TestClient) -> None:
    client.app.state.resources.settings.nexus_enable_voice = False
    with client.websocket_connect("/ws/voice") as ws:
        assert ws.receive_json()["code"] == "VOICE_DISABLED"


def test_untrusted_browser_origin_is_rejected(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(
            "/ws/voice", headers={"origin": "https://evil.test"}
        ):
            pass
    assert error.value.code == 4403


def test_cancel_releases_capacity(client: TestClient) -> None:
    with client.websocket_connect("/ws/voice") as first:
        first.receive_json()
        with client.websocket_connect("/ws/voice") as second:
            assert second.receive_json()["code"] == "VOICE_BUSY"
        first.send_json({"type": "cancel"})
        assert first.receive_json()["type"] == "cancelled"
    with client.websocket_connect("/ws/voice") as third:
        assert third.receive_json()["type"] == "ready"


class BlockingProvider:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.cancelled = threading.Event()

    async def transcribe(self, pcm: bytes) -> Transcript:
        self.started.set()
        try:
            await asyncio.Future[None]()
        finally:
            self.cancelled.set()
        raise AssertionError("Should be cancelled")


@pytest.mark.parametrize("disconnect", [False, True])
def test_interrupt_cancels_pending_inference(
    client: TestClient, disconnect: bool
) -> None:
    provider = BlockingProvider()
    client.app.state.resources.voice_service.provider = provider
    with client.websocket_connect("/ws/voice") as ws:
        ws.receive_json()
        ws.send_bytes(b"\0" * 8000)
        ws.send_json({"type": "finish"})
        assert ws.receive_json()["type"] == "transcribing"
        assert provider.started.wait(2)
        if disconnect:
            ws.close()
        else:
            ws.send_json({"type": "cancel"})
            assert ws.receive_json()["type"] == "cancelled"
        assert provider.cancelled.wait(2)


def test_inference_timeout_cleans_up(client: TestClient) -> None:
    provider = BlockingProvider()
    client.app.state.resources.voice_service.provider = provider
    client.app.state.resources.voice_service.timeout_seconds = 0.01
    with client.websocket_connect("/ws/voice") as ws:
        ws.receive_json()
        ws.send_bytes(b"\0" * 8000)
        ws.send_json({"type": "finish"})
        ws.receive_json()
        assert ws.receive_json()["code"] == "VOICE_TIMEOUT"
    assert provider.cancelled.is_set()


def test_wav_header_matches_wire_audio() -> None:
    pcm = b"\x01\x02" * 4000
    with wave.open(io.BytesIO(pcm_to_wav(pcm))) as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (
            16000,
            1,
            2,
        )
        assert wav.readframes(4000) == pcm


async def test_whisper_adapter_uses_only_configured_server() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://speech.test/inference"
        assert b"audio/wav" in request.content
        assert b"RIFF" in request.content
        assert b"json" in request.content
        return httpx.Response(200, json={"text": "  Plan my study session  "})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await WhisperCppProvider(http, "http://speech.test/").transcribe(
            b"\0\0"
        )
    assert result.text == "Plan my study session"
    assert not result.is_mock


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503, text="secret upstream details"),
        httpx.Response(200, json={"text": 42}),
        httpx.Response(200, content=b"x" * 65537),
    ],
)
async def test_provider_failures_are_sanitized(response: httpx.Response) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: response)
    ) as http:
        with pytest.raises(VoiceError, match="Speech transcription is unavailable"):
            await WhisperCppProvider(http, "http://speech.test").transcribe(b"\0\0")
