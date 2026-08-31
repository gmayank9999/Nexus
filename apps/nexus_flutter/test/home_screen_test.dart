import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/home/presentation/home_screen.dart';
import 'package:nexus_flutter/features/missions/application/mission_controller.dart';
import 'package:nexus_flutter/features/missions/data/mission_api.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';
import 'package:nexus_flutter/features/system_status/application/system_health_provider.dart';
import 'package:nexus_flutter/features/system_status/domain/system_health.dart';
import 'package:nexus_flutter/theme/nexus_theme.dart';

void main() {
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
          missionApiProvider.overrideWithValue(_FakeMissionApi()),
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
  });
}

class _FakeMissionApi implements MissionApi {
  @override
  Future<MissionRun> startMission(String goal) async {
    return const MissionRun(
      id: 'run_test',
      goal: 'Create a task to learn Flutter',
      status: MissionRunStatus.completed,
      steps: [MissionStep(title: 'Create task', tool: 'create_task')],
      traceCount: 8,
      finalResponse: 'Created task: Learn Flutter.',
    );
  }
}
