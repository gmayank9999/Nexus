import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, ValidationError

from app.voice.provider import (
    MAX_FRAME_BYTES,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    Transcript,
    VoiceError,
    VoiceProvider,
)


class VoiceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["finish", "cancel"]


class VoiceService:
    """Per-process capacity limit; sessions keep audio only in bounded memory."""

    def __init__(
        self,
        provider: VoiceProvider,
        *,
        max_sessions: int,
        max_seconds: int,
        timeout_seconds: float,
    ) -> None:
        self.provider = provider
        self.max_sessions = max_sessions
        self.max_seconds = max_seconds
        self.timeout_seconds = timeout_seconds
        self._active = 0

    @asynccontextmanager
    async def reserve(self) -> AsyncIterator[None]:
        # No await between check and increment: atomic within the event loop.
        if self._active >= self.max_sessions:
            raise VoiceError("VOICE_BUSY", "All voice sessions are busy. Try again.")
        self._active += 1
        try:
            yield
        finally:
            self._active -= 1

    async def run(self, websocket: WebSocket) -> None:
        await websocket.send_json(
            {
                "type": "ready",
                "format": "pcm_s16le",
                "sample_rate": SAMPLE_RATE,
                "channels": 1,
                "max_seconds": self.max_seconds,
                "max_frame_bytes": MAX_FRAME_BYTES,
            }
        )
        audio = bytearray()
        try:
            async with asyncio.timeout(self.max_seconds + 10):
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    chunk = message.get("bytes")
                    if chunk is not None:
                        if not chunk or len(chunk) > MAX_FRAME_BYTES or len(chunk) % 2:
                            raise VoiceError(
                                "INVALID_AUDIO", "Invalid PCM16 audio frame."
                            )
                        if len(audio) + len(chunk) > self.max_seconds * SAMPLE_RATE * 2:
                            raise VoiceError(
                                "AUDIO_LIMIT", "Recording duration exceeded."
                            )
                        audio.extend(chunk)
                        continue
                    command = self._command(message.get("text"))
                    if command.type == "cancel":
                        await websocket.send_json({"type": "cancelled"})
                        return
                    break
            if len(audio) < SAMPLE_RATE * SAMPLE_WIDTH // 4:
                raise VoiceError("AUDIO_TOO_SHORT", "Record at least a quarter second.")
            await websocket.send_json({"type": "transcribing"})
            transcript = await self._transcribe_or_cancel(websocket, bytes(audio))
            if transcript is not None:
                if not transcript.text:
                    raise VoiceError(
                        "NO_SPEECH", "No speech detected. Please try again."
                    )
                await websocket.send_json(
                    {
                        "type": "transcript",
                        **transcript.model_dump(),
                    }
                )
        except TimeoutError as exc:
            raise VoiceError(
                "VOICE_TIMEOUT", "Voice session timed out. Try again."
            ) from exc
        finally:
            audio.clear()

    @staticmethod
    def _command(text: str | None) -> VoiceCommand:
        if text is None or len(text) > 128:
            raise VoiceError("INVALID_MESSAGE", "Expected finish or cancel command.")
        try:
            return VoiceCommand.model_validate_json(text)
        except ValidationError as exc:
            raise VoiceError(
                "INVALID_MESSAGE", "Expected finish or cancel command."
            ) from exc

    async def _transcribe_or_cancel(
        self,
        websocket: WebSocket,
        pcm: bytes,
    ) -> Transcript | None:
        transcription = asyncio.create_task(self.provider.transcribe(pcm))
        incoming = asyncio.create_task(websocket.receive())
        try:
            async with asyncio.timeout(self.timeout_seconds):
                completed, _ = await asyncio.wait(
                    {transcription, incoming},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                # Cancellation wins if a transcript arrives at the same instant.
                if incoming in completed:
                    message = incoming.result()
                    if message["type"] == "websocket.disconnect":
                        return None
                    if self._command(message.get("text")).type != "cancel":
                        raise VoiceError(
                            "INVALID_MESSAGE", "Only cancel is allowed now."
                        )
                    await websocket.send_json({"type": "cancelled"})
                    return None
                return transcription.result()
        finally:
            for task in (transcription, incoming):
                task.cancel()
            await asyncio.gather(transcription, incoming, return_exceptions=True)


async def serve_voice(websocket: WebSocket, service: VoiceService) -> None:
    try:
        async with service.reserve():
            await service.run(websocket)
    except VoiceError as exc:
        await websocket.send_json(
            {
                "type": "error",
                "code": exc.code,
                "message": str(exc),
            }
        )
    except WebSocketDisconnect:
        return
