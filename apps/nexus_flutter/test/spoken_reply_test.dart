import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/voice/application/speech_controller.dart';
import 'package:nexus_flutter/features/voice/data/speech_output.dart';
import 'package:nexus_flutter/features/voice/presentation/spoken_reply.dart';

void main() {
  testWidgets('reply never autoplays and exposes explicit read/stop controls', (
    tester,
  ) async {
    final output = _Output();
    await tester.pumpWidget(_app(output));
    expect(output.texts, isEmpty);
    expect(find.textContaining('may process text online'), findsOneWidget);
    await tester.tap(find.text('Read reply aloud'));
    await tester.pumpAndSettle();
    expect(output.texts, ['Mission finished']);
    expect(find.text('Stop reading'), findsOneWidget);
    await tester.tap(find.text('Stop reading'));
    await tester.pumpAndSettle();
    expect(find.text('Read reply aloud'), findsOneWidget);
    expect(output.stops, greaterThanOrEqualTo(2));
  });

  testWidgets('backgrounding stops playback', (tester) async {
    final output = _Output();
    await tester.pumpWidget(_app(output));
    await tester.tap(find.text('Read reply aloud'));
    await tester.pumpAndSettle();
    final stops = output.stops;
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pumpAndSettle();
    expect(output.stops, greaterThan(stops));
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpAndSettle();
    expect(find.text('Read reply aloud'), findsOneWidget);
  });

  testWidgets(
    'leaving the reply stops sound without provider lifecycle errors',
    (tester) async {
      final output = _Output();
      await tester.pumpWidget(_app(output));
      await tester.tap(find.text('Read reply aloud'));
      await tester.pumpAndSettle();
      final stops = output.stops;
      await tester.pumpWidget(const SizedBox());
      await tester.pump();
      expect(output.stops, greaterThan(stops));
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('long responses disclose the excerpt limit', (tester) async {
    final output = _Output();
    await tester.pumpWidget(_app(output, text: 'a' * 4001));
    expect(find.text('Read first 4000 characters'), findsOneWidget);
  });
}

Widget _app(_Output output, {String text = 'Mission finished'}) =>
    ProviderScope(
      overrides: [speechOutputFactoryProvider.overrideWithValue(() => output)],
      child: MaterialApp(
        home: Scaffold(
          body: SpokenReply(sourceId: 'run', text: text),
        ),
      ),
    );

class _Output implements SpeechOutput {
  final texts = <String>[];
  Completer<void>? current;
  int stops = 0;
  @override
  Future<void> speak(String text) async {
    texts.add(text);
    current = Completer<void>();
    await current!.future;
  }

  @override
  Future<void> stop() async {
    stops++;
    if (current != null && !current!.isCompleted) current!.complete();
  }

  @override
  Future<void> dispose() => stop();
}
