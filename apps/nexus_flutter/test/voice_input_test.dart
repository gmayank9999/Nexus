import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/voice/application/voice_controller.dart';
import 'package:nexus_flutter/features/voice/data/realtime_session.dart';
import 'package:nexus_flutter/features/voice/domain/voice_state.dart';
import 'package:nexus_flutter/features/voice/presentation/voice_input.dart';

void main() {
  testWidgets('record, stop, review transcript with an explicit mock label', (
    tester,
  ) async {
    final session = _Session();
    addTearDown(session.events.close);
    final transcripts = <String>[];
    await tester.pumpWidget(_app(session, transcripts.add));
    await tester.tap(find.text('Speak'));
    await tester.pumpAndSettle();
    expect(find.text('Done recording'), findsOneWidget);
    await tester.tap(find.text('Done recording'));
    await tester.pump();
    expect(find.textContaining('Transcribing'), findsOneWidget);
    session.events.add(
      const VoiceState(
        phase: VoicePhase.review,
        text: 'Study Flutter',
        isMock: true,
      ),
    );
    await tester.pump();
    expect(transcripts, ['Study Flutter']);
    expect(find.textContaining('not speech recognition'), findsOneWidget);
  });

  testWidgets('cancel ignores a late transcript and allows a new recording', (
    tester,
  ) async {
    final session = _Session();
    addTearDown(session.events.close);
    final transcripts = <String>[];
    await tester.pumpWidget(_app(session, transcripts.add));
    await tester.tap(find.text('Speak'));
    await tester.pumpAndSettle();
    expect(find.text('Done recording'), findsOneWidget);
    await tester.tap(find.text('Cancel voice'));
    await tester.pump();
    session.events.add(
      const VoiceState(phase: VoicePhase.review, text: 'Too late'),
    );
    await tester.pump();
    expect(transcripts, isEmpty);
    expect(session.closed, isTrue);
    expect(find.text('Speak'), findsOneWidget);
  });

  testWidgets('leaving voice input releases the session', (tester) async {
    final session = _Session();
    addTearDown(session.events.close);
    await tester.pumpWidget(_app(session, (_) {}));
    await tester.tap(find.text('Speak'));
    await tester.pumpAndSettle();
    await tester.pumpWidget(const SizedBox());
    await tester.pump();
    expect(session.closed, isTrue);
  });

  testWidgets('backgrounding cancels the microphone', (tester) async {
    final session = _Session();
    addTearDown(session.events.close);
    await tester.pumpWidget(_app(session, (_) {}));
    await tester.tap(find.text('Speak'));
    await tester.pumpAndSettle();
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump();
    expect(session.closed, isTrue);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
  });
}

Widget _app(_Session session, ValueChanged<String> onTranscript) =>
    ProviderScope(
      overrides: [voiceSessionFactoryProvider.overrideWithValue(() => session)],
      child: MaterialApp(
        home: Scaffold(body: VoiceInput(onTranscript: onTranscript)),
      ),
    );

class _Session implements VoiceSession {
  final events = StreamController<VoiceState>.broadcast();
  bool closed = false;
  @override
  Stream<VoiceState> get updates => events.stream;
  @override
  Future<void> start() async {
    events.add(const VoiceState(phase: VoicePhase.recording));
  }

  @override
  Future<void> finish() async {
    events.add(const VoiceState(phase: VoicePhase.transcribing));
  }

  @override
  Future<void> close() async {
    closed = true;
  }
}
