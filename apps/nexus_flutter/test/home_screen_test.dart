import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/home/presentation/home_screen.dart';
import 'package:nexus_flutter/features/missions/application/follow_up_controller.dart';
import 'package:nexus_flutter/features/missions/application/mission_controller.dart';
import 'package:nexus_flutter/features/missions/data/mission_api.dart';
import 'package:nexus_flutter/features/missions/domain/mission_event.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';
import 'package:nexus_flutter/features/system_status/application/system_health_provider.dart';
import 'package:nexus_flutter/features/system_status/domain/system_health.dart';
import 'package:nexus_flutter/features/voice/application/voice_controller.dart';
import 'package:nexus_flutter/features/voice/data/realtime_session.dart';
import 'package:nexus_flutter/features/voice/domain/voice_state.dart';
import 'package:nexus_flutter/theme/nexus_theme.dart';

void main() {
  testWidgets('spoken goal is editable and never starts without confirmation', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(900, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final api = _FakeMissionApi();
    final voice = _FakeVoiceSession();
    addTearDown(voice.events.close);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          missionApiProvider.overrideWithValue(api),
          voiceSessionFactoryProvider.overrideWithValue(() => voice),
          systemHealthProvider.overrideWith(
            (ref) async => const SystemHealth(
              api: ServiceState.online,
              postgres: ServiceState.online,
              redis: ServiceState.online,
              version: '0.1.0',
            ),
          ),
        ],
        child: MaterialApp(
          theme: NexusTheme.dark,
          home: const Scaffold(body: HomeScreen()),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Speak'));
    await tester.pumpAndSettle();
    expect(tester.widget<TextField>(find.byType(TextField)).readOnly, isTrue);
    expect(api.submittedGoals, isEmpty);
    await tester.tap(find.text('Done recording'));
    await tester.pumpAndSettle();
    expect(find.text('Study Flutter'), findsOneWidget);
    expect(api.submittedGoals, isEmpty);
    await tester.enterText(find.byType(TextField), 'Study Flutter tomorrow');
    await tester.pump();
    await tester.tap(find.text('Start mission'));
    await tester.pumpAndSettle();
    expect(api.submittedGoals, ['Study Flutter tomorrow']);
    await tester.tap(find.text('Follow up'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Speak'));
    await tester.pumpAndSettle();
    // Stream cancellation can complete outside the widget test's fake clock.
    await tester.runAsync(() => Future<void>.delayed(Duration.zero));
    await tester.pumpAndSettle();
    final secondVoiceState = ProviderScope.containerOf(
      tester.element(find.byType(HomeScreen)),
    ).read(voiceControllerProvider);
    expect(
      voice.starts,
      2,
      reason: 'Expected a second session start; closes=${voice.closes}',
    );
    expect(
      secondVoiceState.phase,
      VoicePhase.recording,
      reason: secondVoiceState.message,
    );
    await tester.tap(find.text('Done recording'));
    await tester.pumpAndSettle();
    expect(api.parents, [null]);
    expect(find.textContaining('Following up:'), findsOneWidget);
    await tester.tap(find.text('Start mission'));
    await tester.pumpAndSettle();
    expect(api.parents, [null, 'run_test']);
  });

  testWidgets('renders the command surface and live system state', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(900, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          systemHealthProvider.overrideWith(
            (ref) async => const SystemHealth(
              api: ServiceState.online,
              postgres: ServiceState.online,
              redis: ServiceState.online,
              version: '0.1.0',
            ),
          ),
        ],
        child: MaterialApp(
          theme: NexusTheme.dark,
          home: const Scaffold(body: HomeScreen()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('NEXUS'), findsOneWidget);
    expect(find.text('What do you want to accomplish?'), findsOneWidget);
    expect(find.text('API v0.1.0'), findsOneWidget);
    expect(find.text('Online'), findsNWidgets(2));
  });

  testWidgets('submits a goal and renders the completed mission', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(900, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final api = _FakeMissionApi();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          systemHealthProvider.overrideWith(
            (ref) async => const SystemHealth(
              api: ServiceState.online,
              postgres: ServiceState.online,
              redis: ServiceState.online,
              version: '0.1.0',
            ),
          ),
          missionApiProvider.overrideWithValue(api),
        ],
        child: MaterialApp(
          theme: NexusTheme.dark,
          home: const Scaffold(body: HomeScreen()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byType(TextField),
      'Create a task to learn Flutter',
    );
    await tester.pump();
    await tester.tap(find.text('Start mission'));
    await tester.pumpAndSettle();

    expect(find.text('Mission completed'), findsOneWidget);
    expect(find.text('Created task: Learn Flutter.'), findsOneWidget);
    expect(find.text('Create task'), findsOneWidget);
    expect(api.parents, [null]);
    await tester.tap(find.text('Follow up'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Following up:'), findsOneWidget);
    expect(api.submittedGoals, hasLength(1));
    await tester.enterText(
      find.byType(TextField),
      'What was the previous result?',
    );
    await tester.pump();
    await tester.tap(find.text('Start mission'));
    await tester.pumpAndSettle();
    expect(api.parents, [null, 'run_test']);
    expect(find.textContaining('Following up:'), findsNothing);
    expect(
      tester.widget<TextField>(find.byType(TextField)).controller!.text,
      isEmpty,
    );
    await tester.tap(find.text('Follow up'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Start without previous context'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'An unrelated goal');
    await tester.pump();
    await tester.tap(find.text('Start mission'));
    await tester.pumpAndSettle();
    expect(api.parents, [null, 'run_test', null]);
  });

  testWidgets('failed follow-up preserves the selected context and draft', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(900, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final api = _FakeMissionApi()..fail = true;
    final container = ProviderContainer(
      overrides: [
        missionApiProvider.overrideWithValue(api),
        systemHealthProvider.overrideWith(
          (ref) async => const SystemHealth(
            api: ServiceState.online,
            postgres: ServiceState.online,
            redis: ServiceState.online,
            version: '0.1.0',
          ),
        ),
      ],
    );
    addTearDown(container.dispose);
    container
        .read(followUpProvider.notifier)
        .select(
          const MissionRun(
            id: 'run_parent',
            goal: 'Earlier goal',
            status: MissionRunStatus.completed,
            steps: [],
            traceCount: 0,
            finalResponse: 'Earlier reply',
          ),
        );
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          theme: NexusTheme.dark,
          home: const Scaffold(body: HomeScreen()),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Follow-up question');
    await tester.pump();
    await tester.tap(find.text('Start mission'));
    await tester.pumpAndSettle();
    expect(find.text('Mission request failed'), findsOneWidget);
    expect(find.textContaining('Following up:'), findsOneWidget);
    expect(
      tester.widget<TextField>(find.byType(TextField)).controller!.text,
      'Follow-up question',
    );
    expect(api.parents, ['run_parent']);
  });
}

class _FakeMissionApi implements MissionApi {
  final submittedGoals = <String>[];
  final parents = <String?>[];
  bool fail = false;
  @override
  Future<List<MissionRun>> listMissions() async => [await startMission('')];

  @override
  Future<MissionRun> getMission(String runId) => startMission('');

  @override
  Future<MissionRun> startMission(String goal, {String? parentRunId}) async {
    submittedGoals.add(goal);
    parents.add(parentRunId);
    if (fail) throw StateError('Request failed');
    return const MissionRun(
      id: 'run_test',
      goal: 'Create a task to learn Flutter',
      status: MissionRunStatus.completed,
      steps: [MissionStep(title: 'Create task', tool: 'create_task')],
      traceCount: 8,
      finalResponse: 'Created task: Learn Flutter.',
    );
  }

  @override
  Stream<MissionEvent> watchMission(String runId, {int after = 0}) {
    return const Stream.empty();
  }

  @override
  Future<MissionRun> approve(String runId) => throw UnimplementedError();

  @override
  Future<MissionRun> cancel(String runId) => throw UnimplementedError();

  @override
  Future<MissionRun> reject(String runId) => throw UnimplementedError();
}

class _FakeVoiceSession implements VoiceSession {
  final events = StreamController<VoiceState>.broadcast();
  int starts = 0;
  int closes = 0;
  @override
  Stream<VoiceState> get updates => events.stream;
  @override
  Future<void> start() async {
    starts++;
    events.add(const VoiceState(phase: VoicePhase.recording));
  }

  @override
  Future<void> finish() async {
    events.add(
      const VoiceState(phase: VoicePhase.review, text: 'Study Flutter'),
    );
  }

  @override
  Future<void> close() async {
    closes++;
  }
}
