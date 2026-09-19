import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/voice/application/speech_controller.dart';
import 'package:nexus_flutter/features/voice/data/realtime_session.dart';
import 'package:nexus_flutter/features/voice/domain/voice_state.dart';

final voiceSessionFactoryProvider = Provider<VoiceSession Function()>(
  (ref) => RealtimeSession.new,
);

final voiceControllerProvider =
    NotifierProvider.autoDispose<VoiceController, VoiceState>(
      VoiceController.new,
    );

class VoiceController extends Notifier<VoiceState> {
  VoiceSession? _session;
  StreamSubscription<VoiceState>? _subscription;
  int _generation = 0;
  int? _captureLease;
  late SpeechController _speech;

  @override
  VoiceState build() {
    _speech = ref.read(speechControllerProvider.notifier);
    ref.onDispose(() {
      _generation++;
      unawaited(_subscription?.cancel());
      unawaited(_closeCapture(_session, _captureLease));
    });
    return const VoiceState();
  }

  Future<void> start() async {
    if (state.isBusy) return;
    final generation = ++_generation;
    final factory = ref.read(voiceSessionFactoryProvider);
    state = const VoiceState(phase: VoicePhase.connecting);
    final lease = _speech.reserveCapture();
    _captureLease = lease;
    final stopped = await _speech.stop();
    if (generation != _generation) return;
    if (!stopped) {
      _speech.releaseCapture(lease);
      state = const VoiceState(
        phase: VoicePhase.error,
        message: 'Stop device speech playback before starting the microphone.',
      );
      return;
    }
    await _subscription?.cancel();
    await _session?.close();
    if (generation != _generation) return;
    final session = factory();
    _session = session;
    _subscription = session.updates.listen((value) {
      if (generation == _generation) {
        if (!value.isBusy) unawaited(_closeCapture(session, lease));
        state = value;
      }
    });
    try {
      await session.start();
    } catch (_) {
      if (generation != _generation) return;
      state = const VoiceState(
        phase: VoicePhase.error,
        message: 'Could not start voice input. Try again.',
      );
      await _closeCapture(session, lease);
    }
  }

  Future<void> finish() async {
    if (state.phase != VoicePhase.recording) return;
    state = const VoiceState(phase: VoicePhase.transcribing);
    await _session?.finish();
  }

  Future<void> cancel() async {
    _generation++;
    final lease = _captureLease;
    _captureLease = null;
    final session = _session;
    _session = null;
    final subscription = _subscription;
    _subscription = null;
    state = const VoiceState();
    // Do not delay releasing the microphone behind stream cancellation.
    final closing = _closeCapture(session, lease);
    await subscription?.cancel();
    await closing;
  }

  Future<void> _closeCapture(VoiceSession? session, int? lease) async {
    try {
      await session?.close();
    } finally {
      if (lease != null) _speech.releaseCapture(lease);
    }
  }
}
