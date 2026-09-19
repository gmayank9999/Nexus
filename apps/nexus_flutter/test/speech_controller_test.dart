import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/voice/application/speech_controller.dart';
import 'package:nexus_flutter/features/voice/application/voice_controller.dart';
import 'package:nexus_flutter/features/voice/data/realtime_session.dart';
import 'package:nexus_flutter/features/voice/data/speech_output.dart';
import 'package:nexus_flutter/features/voice/domain/voice_state.dart';

void main() {
  test('playback is lazy, bounded, and returns idle on completion', () async {
    final fixture = _Fixture();
    addTearDown(fixture.close);
    expect(fixture.created, 0);
    final playing = fixture.speech.play('run', '😀' * 4100);
    await _until(() => fixture.output.texts.isNotEmpty);
    expect(fixture.created, 1);
    expect(fixture.output.texts.single.runes.length, 4000);
    expect(fixture.state.phase, SpeechPhase.speaking);
    fixture.output.requests.single.complete();
    await playing;
    expect(fixture.state.phase, SpeechPhase.idle);
  });

  test('cancel during preparation prevents delayed playback', () async {
    final fixture = _Fixture();
    addTearDown(fixture.close);
    fixture.output.stopGate = Completer<void>();
    final playing = fixture.speech.play('run', 'Do not play');
    final stopping = fixture.speech.stop();
    fixture.output.stopGate!.complete();
    await Future.wait([playing, stopping]);
    expect(fixture.output.texts, isEmpty);
    expect(fixture.state.isBusy, isFalse);
  });

  test('an old completion cannot clear the newest reply', () async {
    final fixture = _Fixture();
    addTearDown(fixture.close);
    final first = fixture.speech.play('first', 'First');
    await _until(() => fixture.output.requests.length == 1);
    final second = fixture.speech.play('second', 'Second');
    await _until(() => fixture.output.requests.length == 2);
    fixture.output.requests.first.complete();
    await first;
    expect(fixture.state.sourceId, 'second');
    fixture.speech.release('first');
    expect(fixture.state.sourceId, 'second');
    fixture.output.requests.last.complete();
    await second;
  });

  test('provider error does not expose response text', () async {
    final fixture = _Fixture();
    addTearDown(fixture.close);
    fixture.output.failSpeak = true;
    await fixture.speech.play('run', 'private response');
    expect(fixture.state.phase, SpeechPhase.error);
    expect(fixture.state.message, isNot(contains('private response')));
  });

  test(
    'capture waits for playback stop and blocks read-aloud until closed',
    () async {
      final fixture = _Fixture();
      addTearDown(fixture.close);
      final playing = fixture.speech.play('run', 'Reply');
      await _until(() => fixture.output.requests.isNotEmpty);
      fixture.output.stopGate = Completer<void>();
      final recording = fixture.voice.start();
      await Future<void>.delayed(Duration.zero);
      expect(fixture.input.started, isFalse);
      await fixture.speech.play('other', 'Must not overlap');
      expect(fixture.output.texts, ['Reply']);
      fixture.output.stopGate!.complete();
      await recording;
      expect(fixture.input.started, isTrue);
      fixture.output.requests.first.complete();
      await playing;
      fixture.input.closeGate = Completer<void>();
      final cancellation = fixture.voice.cancel();
      await fixture.speech.play('other', 'Still closing microphone');
      expect(fixture.output.texts, ['Reply']);
      fixture.input.closeGate!.complete();
      await cancellation;
      final next = fixture.speech.play('next', 'Now safe');
      await _until(() => fixture.output.requests.length == 2);
      fixture.output.requests.last.complete();
      await next;
    },
  );

  test('failed output stop prevents opening the microphone', () async {
    final fixture = _Fixture();
    addTearDown(fixture.close);
    final playing = fixture.speech.play('run', 'Reply');
    await _until(() => fixture.output.requests.isNotEmpty);
    fixture.output.failStop = true;
    await fixture.voice.start();
    expect(fixture.input.started, isFalse);
    expect(
      fixture.container.read(voiceControllerProvider).phase,
      VoicePhase.error,
    );
    fixture.output.requests.single.complete();
    await playing;
  });

  test('releasing one capture reservation cannot release another', () async {
    final fixture = _Fixture();
    addTearDown(fixture.close);
    final first = fixture.speech.reserveCapture();
    final second = fixture.speech.reserveCapture();
    fixture.speech.releaseCapture(first);
    await fixture.speech.play('run', 'Blocked');
    expect(fixture.created, 0);
    fixture.speech.releaseCapture(second);
    final playing = fixture.speech.play('run', 'Allowed');
    await _until(() => fixture.output.requests.isNotEmpty);
    fixture.output.requests.single.complete();
    await playing;
  });
}

Future<void> _until(bool Function() done) async {
  for (var tries = 0; tries < 100; tries++) {
    if (done()) return;
    await Future<void>.delayed(const Duration(milliseconds: 2));
  }
  fail('Speech state did not settle');
}

class _Fixture {
  _Fixture() {
    container = ProviderContainer(
      overrides: [
        speechOutputFactoryProvider.overrideWithValue(() {
          created++;
          return output;
        }),
        voiceSessionFactoryProvider.overrideWithValue(() => input),
      ],
    );
    keepVoice = container.listen(voiceControllerProvider, (_, _) {});
    speech = container.read(speechControllerProvider.notifier);
    voice = container.read(voiceControllerProvider.notifier);
  }
  final output = _Output();
  final input = _Input();
  int created = 0;
  late final ProviderContainer container;
  late final ProviderSubscription<VoiceState> keepVoice;
  late final SpeechController speech;
  late final VoiceController voice;
  SpeechState get state => container.read(speechControllerProvider);
  Future<void> close() async {
    keepVoice.close();
    container.dispose();
    await input.events.close();
  }
}

class _Output implements SpeechOutput {
  final texts = <String>[];
  final requests = <Completer<void>>[];
  Completer<void>? stopGate;
  bool failStop = false;
  bool failSpeak = false;
  @override
  Future<void> speak(String text) async {
    if (failSpeak) throw StateError('private response');
    texts.add(text);
    final request = Completer<void>();
    requests.add(request);
    await request.future;
  }

  @override
  Future<void> stop() async {
    if (failStop) throw StateError('Device refused stop');
    await stopGate?.future;
  }

  @override
  Future<void> dispose() async {
    for (final request in requests) {
      if (!request.isCompleted) request.complete();
    }
  }
}

class _Input implements VoiceSession {
  final events = StreamController<VoiceState>.broadcast();
  bool started = false;
  Completer<void>? closeGate;
  @override
  Stream<VoiceState> get updates => events.stream;
  @override
  Future<void> start() async {
    started = true;
    events.add(const VoiceState(phase: VoicePhase.recording));
  }

  @override
  Future<void> finish() async {}
  @override
  Future<void> close() async {
    await closeGate?.future;
  }
}
