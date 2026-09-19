import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
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

  @override
  VoiceState build() {
    ref.onDispose(() {
      _generation++;
      unawaited(_subscription?.cancel());
      unawaited(_session?.close());
    });
    return const VoiceState();
  }

  Future<void> start() async {
    if (state.isBusy) return;
    final generation = ++_generation;
    final factory = ref.read(voiceSessionFactoryProvider);
    state = const VoiceState(phase: VoicePhase.connecting);
    await _subscription?.cancel();
    await _session?.close();
    if (generation != _generation) return;
    final session = factory();
    _session = session;
    _subscription = session.updates.listen((value) {
      if (generation == _generation) state = value;
    });
    await session.start();
  }

  Future<void> finish() async {
    if (state.phase != VoicePhase.recording) return;
    state = const VoiceState(phase: VoicePhase.transcribing);
    await _session?.finish();
  }

  Future<void> cancel() async {
    _generation++;
    final session = _session;
    _session = null;
    final subscription = _subscription;
    _subscription = null;
    state = const VoiceState();
    // Do not delay releasing the microphone behind stream cancellation.
    final closing = session?.close();
    await subscription?.cancel();
    await closing;
  }
}
