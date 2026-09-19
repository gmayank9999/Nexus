import io
import wave
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2
MAX_FRAME_BYTES = 65_536


class VoiceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class Transcript(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(max_length=4000)
    is_mock: bool = False


class VoiceProvider(Protocol):
    async def transcribe(self, pcm: bytes) -> Transcript: ...


def pcm_to_wav(pcm: bytes) -> bytes:
    """Wrap validated mono PCM16LE; no user paths or media subprocesses."""
    if not pcm or len(pcm) % SAMPLE_WIDTH:
        raise VoiceError("INVALID_AUDIO", "Audio must contain complete PCM16 samples.")
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)
    return output.getvalue()


class WhisperCppProvider:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._url = f"{base_url.rstrip('/')}/inference"

    async def transcribe(self, pcm: bytes) -> Transcript:
        try:
            # The session enforces the overall deadline, including streamed reads.
            async with self._client.stream(
                "POST",
                self._url,
                files={"file": ("speech.wav", pcm_to_wav(pcm), "audio/wav")},
                data={"response_format": "json", "temperature": "0.0"},
                timeout=None,
            ) as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 65_536:
                        raise ValueError("Oversized transcription response")
                return Transcript.model_validate_json(body)
        except (httpx.HTTPError, ValueError) as exc:
            # Do not expose endpoint credentials, provider bodies, or audio.
            raise VoiceError(
                "VOICE_PROVIDER_UNAVAILABLE", "Speech transcription is unavailable."
            ) from exc


class MockVoiceProvider:
    async def transcribe(self, pcm: bytes) -> Transcript:
        pcm_to_wav(pcm)
        return Transcript(
            text="Create a task to learn Flutter architecture", is_mock=True
        )
