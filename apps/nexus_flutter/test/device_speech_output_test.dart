import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:nexus_flutter/features/voice/data/device_speech_output.dart';
import 'package:nexus_flutter/features/voice/data/speech_output.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('flutter_tts');
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;

  tearDown(() {
    messenger.setMockMethodCallHandler(channel, null);
    debugDefaultTargetPlatformOverride = null;
  });

  test('engine failure during setup never sends the reply to speak', () async {
    final ready = Completer<void>();
    final setup = Completer<int>();
    final calls = <String>[];
    messenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call.method);
      if (call.method == 'awaitSpeakCompletion') {
        ready.complete();
        return setup.future;
      }
      return 1;
    });
    final engine = FlutterTts();
    final output = DeviceSpeechOutput(createEngine: () => engine);
    final speaking = output.speak('Do not synthesize');
    final expectation = expectLater(speaking, throwsA(isA<StateError>()));
    await ready.future;
    await engine.platformCallHandler(
      const MethodCall('speak.onError', 'Device error'),
    );
    setup.complete(1);
    await expectation;
    expect(calls, isNot(contains('speak')));
    await output.dispose();
  });

  test(
    'adapter waits for completion and stops a never-completing utterance',
    () async {
      final calls = <String>[];
      final nativeCompletion = Completer<int>();
      final started = Completer<void>();
      messenger.setMockMethodCallHandler(channel, (call) async {
        calls.add(call.method);
        if (call.method == 'speak') {
          started.complete();
          return nativeCompletion.future;
        }
        return 1;
      });
      final output = DeviceSpeechOutput();
      final speaking = output.speak('A completed mission reply');
      await started.future;
      await output.stop();
      await speaking;
      expect(calls, ['awaitSpeakCompletion', 'setSpeechRate', 'speak', 'stop']);
      nativeCompletion.complete(1);
      await output.dispose();
    },
  );

  test('cancelling during engine setup cannot later call speak', () async {
    final gate = Completer<int>();
    final setup = Completer<void>();
    final calls = <String>[];
    messenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call.method);
      if (call.method == 'awaitSpeakCompletion') {
        setup.complete();
        return gate.future;
      }
      return 1;
    });
    final output = DeviceSpeechOutput();
    final speaking = output.speak('Must not be spoken');
    await setup.future;
    await output.stop();
    gate.complete(1);
    await speaking;
    expect(calls, isNot(contains('speak')));
    await output.dispose();
  });

  test(
    'platform callback errors reject playback without leaking details',
    () async {
      final started = Completer<void>();
      final nativeCompletion = Completer<int>();
      messenger.setMockMethodCallHandler(channel, (call) async {
        if (call.method == 'speak') {
          started.complete();
          return nativeCompletion.future;
        }
        return 1;
      });
      final engine = FlutterTts();
      final output = DeviceSpeechOutput(createEngine: () => engine);
      final speaking = output.speak('Sensitive reply');
      final expectation = expectLater(speaking, throwsA(isA<StateError>()));
      await started.future;
      await engine.platformCallHandler(
        const MethodCall('speak.onError', 'Sensitive reply'),
      );
      await expectation;
      nativeCompletion.complete(1);
      await output.dispose();
    },
  );

  test(
    'Windows remains gated without initializing its speech engine',
    () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.windows;
      var created = false;
      final output = DeviceSpeechOutput(
        createEngine: () {
          created = true;
          return FlutterTts();
        },
      );
      await expectLater(
        output.speak('Reply'),
        throwsA(isA<SpeechOutputUnavailable>()),
      );
      expect(created, isFalse);
      await output.dispose();
    },
  );
}
