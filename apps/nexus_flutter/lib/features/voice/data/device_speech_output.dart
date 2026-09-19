import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:nexus_flutter/features/voice/data/speech_output.dart';

/// Explicitly invoked platform speech. The selected OS/browser voice may use
/// network services; the UI discloses this before the user requests playback.
class DeviceSpeechOutput implements SpeechOutput {
  DeviceSpeechOutput({FlutterTts Function()? createEngine})
    : _createEngine = createEngine ?? FlutterTts.new;

  final FlutterTts Function() _createEngine;
  FlutterTts? _engine;
  Completer<void>? _interrupted;
  int _generation = 0;
  bool _disposed = false;

  @override
  Future<void> speak(String text) async {
    if (_disposed) throw StateError('Speech output is closed.');
    // Windows synthesis in this plugin can resume after stop. Keep that adapter
    // disabled until native interruption has been verified.
    if (!kIsWeb && defaultTargetPlatform != TargetPlatform.android) {
      throw const SpeechOutputUnavailable(
        'Device read-aloud is available on Android and web. Use the web app on this device.',
      );
    }
    final generation = ++_generation;
    final interrupted = Completer<void>();
    // Platform errors can arrive while the setup calls are still in flight.
    interrupted.future.ignore();
    _interrupted = interrupted;
    final engine = _engine ??= _createEngine();
    engine.setErrorHandler((_) {
      if (generation == _generation && !interrupted.isCompleted) {
        interrupted.completeError(
          StateError('The device speech engine failed.'),
        );
      }
    });
    try {
      await engine
          .awaitSpeakCompletion(true)
          .timeout(const Duration(seconds: 5));
      if (generation != _generation) return;
      if (interrupted.isCompleted) {
        await interrupted.future;
        return;
      }
      await engine.setSpeechRate(0.5).timeout(const Duration(seconds: 5));
      if (generation != _generation) return;
      if (interrupted.isCompleted) {
        await interrupted.future;
        return;
      }
      final completion = engine.speak(text).then<void>((result) {
        if (result == 0) throw StateError('Speech playback could not start.');
      });
      // Some engines never resolve speak() on cancellation. Do not wait for it.
      await Future.any([
        completion,
        interrupted.future,
      ]).timeout(const Duration(minutes: 2));
    } finally {
      if (generation == _generation) _interrupted = null;
    }
  }

  @override
  Future<void> stop() async {
    _generation++;
    final interrupted = _interrupted;
    _interrupted = null;
    if (interrupted != null && !interrupted.isCompleted) interrupted.complete();
    final engine = _engine;
    if (engine != null) {
      final result = await engine.stop().timeout(const Duration(seconds: 3));
      if (result == 0) {
        throw StateError('The device could not stop speech playback.');
      }
    }
  }

  @override
  Future<void> dispose() async {
    _disposed = true;
    await stop();
  }
}
