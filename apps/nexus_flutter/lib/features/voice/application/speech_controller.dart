import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/voice/data/device_speech_output.dart';
import 'package:nexus_flutter/features/voice/data/speech_output.dart';

final speechOutputFactoryProvider = Provider<SpeechOutput Function()>(
  (ref) => DeviceSpeechOutput.new,
);

// One owner for the platform speech channel across Home and mission details.
// The engine itself is created lazily, only after a user presses Read reply.
final speechControllerProvider =
    NotifierProvider<SpeechController, SpeechState>(SpeechController.new);

enum SpeechPhase { idle, preparing, speaking, error }

class SpeechState {
  const SpeechState({
    this.phase = SpeechPhase.idle,
    this.sourceId,
    this.message,
  });
  final SpeechPhase phase;
  final String? sourceId;
  final String? message;
  bool get isBusy =>
      phase == SpeechPhase.preparing || phase == SpeechPhase.speaking;
}

const maxSpokenCharacters = 4000;

String spokenExcerpt(String text) =>
    String.fromCharCodes(text.trim().runes.take(maxSpokenCharacters));

class SpeechController extends Notifier<SpeechState> {
  SpeechOutput? _output;
  Future<void>? _stopping;
  int _generation = 0;
  bool _disposed = false;
  final _captureLeases = <int>{};
  int _nextLease = 0;

  @override
  SpeechState build() {
    ref.onDispose(() {
      _disposed = true;
      _generation++;
      final output = _output;
      if (output != null) unawaited(output.dispose().catchError((Object _) {}));
    });
    return const SpeechState();
  }

  Future<void> play(String sourceId, String text) async {
    final excerpt = spokenExcerpt(text);
    if (_captureLeases.isNotEmpty || excerpt.isEmpty || _disposed) return;
    final generation = ++_generation;
    state = SpeechState(phase: SpeechPhase.preparing, sourceId: sourceId);
    try {
      _output ??= ref.read(speechOutputFactoryProvider)();
      await _halt();
      if (!_current(generation)) return;
      state = SpeechState(phase: SpeechPhase.speaking, sourceId: sourceId);
      await _output!.speak(excerpt);
      if (_current(generation)) state = const SpeechState();
    } catch (error) {
      if (!_current(generation)) return;
      // Also stop a backend that timed out without a completion callback.
      try {
        await _halt();
      } catch (_) {
        /* Report a safe, actionable error below. */
      }
      if (_current(generation)) {
        state = SpeechState(
          phase: SpeechPhase.error,
          sourceId: sourceId,
          message: error is SpeechOutputUnavailable
              ? error.message
              : 'Speech playback failed. Check your device voice settings, or read the reply on screen.',
        );
      }
    }
  }

  /// Returns false if capture must not proceed because output could not stop.
  Future<bool> stop({String? sourceId}) async {
    if (_disposed) return false;
    if (sourceId != null && state.sourceId != sourceId) return true;
    final generation = ++_generation;
    final owner = state.sourceId;
    state = const SpeechState();
    try {
      await _halt();
      return true;
    } catch (_) {
      if (_current(generation)) {
        state = SpeechState(
          phase: SpeechPhase.error,
          sourceId: owner,
          message:
              'Could not stop device speech. Check your device audio controls before recording.',
        );
      }
      return false;
    }
  }

  int reserveCapture() {
    final lease = ++_nextLease;
    _captureLeases.add(lease);
    return lease;
  }

  void releaseCapture(int lease) {
    _captureLeases.remove(lease);
  }

  /// Widget disposal must stop audio immediately without synchronously changing
  /// provider state during a Flutter build. An old screen cannot stop a new owner.
  void release(String sourceId) {
    if (_disposed) return;
    if (state.sourceId != sourceId) return;
    final generation = ++_generation;
    final stopping = _halt();
    unawaited(stopping.catchError((Object _) {}));
    scheduleMicrotask(() async {
      try {
        await stopping;
        if (_current(generation)) state = const SpeechState();
      } catch (_) {
        if (_current(generation)) {
          state = SpeechState(
            phase: SpeechPhase.error,
            sourceId: sourceId,
            message:
                'Device speech could not be stopped. Check your audio controls.',
          );
        }
      }
    });
  }

  Future<void> _halt() {
    final output = _output;
    if (output == null) return Future.value();
    return _stopping ??= Future.sync(output.stop).whenComplete(() {
      _stopping = null;
    });
  }

  bool _current(int generation) => !_disposed && generation == _generation;
}
