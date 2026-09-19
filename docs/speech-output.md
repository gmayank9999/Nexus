# Spoken replies (Phase 6, second slice)

Completed mission replies have an explicit **Read reply aloud** control in Home
and mission details. Nothing plays automatically. Press **Stop reading** to
interrupt. Starting microphone capture stops output first; a failed stop keeps
the microphone closed. Playback also stops when the reply changes, its screen
is removed, or the application is backgrounded. Stopping sound does not cancel
an agent mission.

## Provider boundary and privacy

`SpeechOutput` defines `speak`, `stop`, and `dispose`. The current
`DeviceSpeechOutput` adapter uses the device/browser's default text-to-speech
engine through [flutter_tts](https://pub.dev/packages/flutter_tts). Voice and
language selection currently follow system/browser settings; there is no
in-app voice picker or server-side synthesis adapter yet.

The text comes from the NEXUS runtime's completed response. Flutter never calls
an LLM for playback. NEXUS does not require speech API credentials, download a
voice model, or save generated audio. However, **the selected system/browser
voice may process text online**. This notice appears beside Read reply. Do not
use it for confidential text unless you trust that engine's processing policy.
Offline-only synthesis is not guaranteed by this adapter.

Read-aloud is a client-side, manually invoked feature independent of the backend
`NEXUS_ENABLE_VOICE` input flag. That flag still controls microphone/transcription
sessions only. A future self-hosted output adapter can replace `SpeechOutput`
without changing the mission runtime or widgets.

## Supported targets

- Android and web: adapter enabled; tests exercise the platform method channel
  and mocked playback. Actual sound/device testing remains outstanding.
- Windows: device playback intentionally disabled. The selected plugin's native
  implementation starts synthesis asynchronously, and its stop path can race
  with pending synthesis. A cancellation-safe Windows adapter needs verification
  before enabling it. The button provides a message directing users to the web
  client. Microphone input is unchanged.
- iOS/macOS/Linux: no application targets or speech verification added here.

Windows builds also still need the Visual Studio C++ toolchain noted in the
[voice input guide](voice.md). The speech plugin's Windows build configuration
requires NuGet and C++/WinRT even though runtime playback is gated.

## State and safety

One Riverpod controller owns platform playback across screens. Each request has
a generation number and a source run ID. Late results cannot change a newer
reply, and disposing an old screen cannot stop a different active run's audio.

Microphone sessions hold independent capture reservations until their close
operation finishes. An old capture finishing cannot release a newer capture's
reservation. Read requests are refused while any reservation remains active.
The platform engine is created lazily on the first explicit Read request.

Speech is limited to the first 4,000 Unicode code points, with an excerpt label
for longer responses. UTF-16 surrogate pairs are not split. A playback request
has a two-minute deadline, setup calls five seconds, and Stop three seconds.
Errors leave the full text readable and do not include provider error payloads
or private response text. System speech engines may pronounce Markdown syntax;
this slice does not produce a separate spoken summary.

## Verification

The regression run passed 41 Flutter tests and 62 backend tests. Flutter analysis
and formatting checks and the release web build also passed. The backend was
unchanged in this slice.

A separate `flutter test --platform chrome test/spoken_reply_test.dart
test/home_screen_test.dart` attempt was blocked before assertions: the Flutter
3.44.7 Windows test server returned HTTP 404 for
`/canvaskit/chromium/canvaskit.js` even though that file exists in the SDK cache.
The browser console reported failed CanvasKit/WASM loading. The dedicated test
browser was stopped; this run is **not** counted as passing. No SDK files were
modified. Retry browser tests on a working test runner (for example Linux CI)
before treating browser-runtime verification as complete.

Tests cover explicit read/stop controls, no autoplay, completion, excerpt limits,
background/navigation cleanup, cancellation during setup, late completion,
platform errors, unsupported-target gating, microphone/output exclusion, and
failure to stop playback. Platform tests mock the speech method channel and do
not use a speaker or transmit response text to a real speech service.

Persisted turn context is now available through [explicit follow-up missions](conversations.md).
Full-duplex dialogue, incremental speech recognition, a self-hosted speech-output
adapter, and real-device/model acceptance testing remain unfinished. Phase 6 is
still in progress.

## Changed files

- `apps/nexus_flutter/lib/features/voice/data/{speech_output,device_speech_output}.dart`
- `apps/nexus_flutter/lib/features/voice/application/{speech_controller,voice_controller}.dart`
- `apps/nexus_flutter/lib/features/voice/presentation/spoken_reply.dart`
- `apps/nexus_flutter/lib/features/home/presentation/home_screen.dart`
- `apps/nexus_flutter/lib/features/missions/presentation/mission_detail_screen.dart`
- `apps/nexus_flutter/test/{device_speech_output,speech_controller,spoken_reply}_test.dart`
- Flutter `pubspec.yaml`, `pubspec.lock`, Android manifest, and generated Windows
  plugin registration files.
- `README.md`, `docs/architecture.md`, `docs/voice.md`, and this guide.
