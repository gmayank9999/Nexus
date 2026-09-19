# Voice input (Phase 6)

Status: speech input and interruptible device read-aloud are implemented;
Phase 6 is **not yet complete**. Conversational turn context, incremental
transcription, and real-device/model verification remain outstanding. The flow
is push-to-talk, review, then explicit mission submission—not full-duplex dialogue.
See [spoken replies](speech-output.md) for supported targets and privacy limits.

## Using it

1. Enable voice on the backend and choose a provider (below).
2. In Home, press **Speak** and allow microphone access.
3. Press **Done recording**, or let the configured recording limit finish it.
4. Review/edit the transcript in the goal field and press **Start mission**.
5. **Cancel voice** discards capture or pending transcription. Once a mission
   starts, use the existing mission Cancel control to stop agent execution.

The microphone is requested only after the backend accepts the session. Leaving
Home or backgrounding the app closes capture. Network failures do not reconnect
or replay microphone data automatically. A demo transcript is explicitly labeled
and never presented as recognized speech.

## Providers and configuration

Voice is disabled by default and is independent of `NEXUS_LLM_PROVIDER`.

```env
NEXUS_ENABLE_VOICE=true
NEXUS_VOICE_PROVIDER=whisper_cpp
NEXUS_WHISPER_BASE_URL=http://localhost:8080
NEXUS_VOICE_MAX_SECONDS=60
NEXUS_VOICE_TIMEOUT_SECONDS=60
NEXUS_VOICE_MAX_SESSIONS=4
```

Run your own whisper.cpp server with an explicitly installed model. NEXUS never
downloads speech models, launches media conversion commands, or sends audio to a
paid provider. Its adapter wraps PCM in WAV and sends a multipart request to the
configured `/inference` endpoint, requesting JSON. See the
[upstream server instructions](https://github.com/ggml-org/whisper.cpp/blob/master/examples/server/README.md).

For Docker Desktop, use `http://host.docker.internal:8080` to reach a host speech
server (the Compose default). Ensure that server listens on an interface the
container can reach, behind your firewall. On Linux, configure a reachable
private service address. Do not expose the speech service publicly or run it
with administrator privileges. No external speech service is bundled in Compose.

For deterministic transport/UI testing without a speech model:

```powershell
$env:NEXUS_LLM_PROVIDER='mock'
$env:NEXUS_ENABLE_VOICE='true'
$env:NEXUS_VOICE_PROVIDER='mock'
docker compose up --build --detach
.\.venv\Scripts\python.exe scripts/voice_smoke.py
```

The smoke script sends synthetic silence, expects a labeled mock transcript,
and explicitly creates a demo mission in the `voice-smoke` workspace. It does
not access a microphone or test transcription accuracy.

## Wire contract

`GET /api/v1/voice/status` returns enablement, provider, final-transcript mode,
and maximum recording length. It reports configuration, not provider health.

One `WS /ws/voice` connection carries one utterance:

1. Server sends `ready`: PCM signed 16-bit little-endian, mono, 16 kHz.
2. Client streams binary PCM frames. Each must contain complete samples and
   be at most 65,536 bytes. Flutter sends frames at most 16,384 bytes.
3. Client sends `{"type":"finish"}`. Server sends `transcribing`, then
   `{"type":"transcript","text":"...","is_mock":false}` and closes.
4. `{"type":"cancel"}` or a disconnect interrupts collection or the pending
   transcription request. Cancellation does not guarantee the upstream speech
   server stops computation; it prevents delivery and releases NEXUS resources.

Audio transport is streamed; this adapter performs recognition after Finish.
There are no partial transcripts yet. Nothing on this socket creates a mission;
reviewed text uses the existing `POST /api/v1/runs` flow and permission policy.

## Limits and privacy

- At least 0.25 seconds of audio; maximum 60 seconds by default (configurable
  1–120). At 16 kHz mono PCM16, the default collection buffer is at most 1.92 MB.
- Recording/session setup has a wall-clock deadline of maximum seconds + 10.
  Inference has a separate deadline. Concurrent sessions default to four per
  API process. This is a local prototype, not a multi-tenant rate limiter.
- Audio stays in application memory and is not written to NEXUS storage/logs.
  A configured speech service has its own retention and logging policy.
- Audio frame limits apply after WebSocket decoding. Configure ingress/Uvicorn
  message and queue limits as well before exposing the API beyond a trusted LAN.
- Browser Origin must exactly match `CORS_ORIGINS`. Native clients without an
  Origin header remain allowed. This check is not authentication.
- Use HTTPS/WSS outside localhost. Browser microphone access requires a secure
  context. Android declares `RECORD_AUDIO` and `INTERNET`; release network access
  should use HTTPS. Windows uses the system microphone privacy controls.
- Flutter uses the [record package](https://pub.dev/packages/record) through an
  injectable microphone interface. No iOS/macOS/Linux app targets have been
  added or verified in this milestone.

## Verification and remaining work

Input-slice verification: 62 backend tests and 25 Flutter tests passed;
backend lint, strict type checks, and Flutter analysis passed. Web compilation and the Docker
mock-voice-to-mission smoke check passed. A Windows release build was attempted
but blocked by the missing Visual Studio C++ toolchain; no Windows build success
is claimed. Install the Flutter Windows development prerequisites and rerun
`flutter build windows --release` before native device verification.
The later read-aloud checks are recorded in [spoken replies](speech-output.md#verification).

Backend tests cover enablement, Origin rejection, protocol errors, frame/duration
limits, admission capacity, WAV format, mock-to-agent submission, timeout, cancel,
disconnect, and sanitized provider errors. HTTP provider tests use mocked
responses; no real whisper.cpp inference was run.

Flutter tests cover actual local WebSocket framing with an injected microphone,
trailing audio flush, byte limits, malformed replies, permission errors, disposal,
late-result rejection, background cancellation, transcript review, and explicit
mission submission. Real microphone capture, native device behavior, transcription
accuracy, and browser visual QA remain unverified.

Typed and spoken goals now support [explicit follow-up context](conversations.md).
End-to-end testing against an explicitly configured local speech model remains
open. A self-hosted output adapter and safe
native Windows playback remain open. Earlier memory/RAG
acceptance gaps remain tracked in [mission notes](missions.md#remaining-work).

## Changed files

- Backend: `app/voice/{provider,session,__init__}.py`, `app/api/routes/voice.py`,
  `app/api/router.py`, `app/config/settings.py`, `app/storage/resources.py`.
- Config: `.env.example`, `infra/docker-compose.yml`.
- Flutter: `lib/features/voice/{application/voice_controller,data/audio_stream_manager,data/realtime_session,domain/voice_state,presentation/voice_input}.dart`,
  `lib/features/home/presentation/home_screen.dart`, `pubspec.yaml`, `pubspec.lock`,
  Android manifest, Windows generated plugin registration files.
- Tests: `tests/test_voice.py`, `test/voice_{input,session}_test.dart`,
  `test/home_screen_test.dart`, `scripts/voice_smoke.py`.
- Docs: this file, `README.md`, `docs/architecture.md`.
