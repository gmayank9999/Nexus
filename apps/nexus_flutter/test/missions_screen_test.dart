import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/missions/application/mission_controller.dart';
import 'package:nexus_flutter/features/missions/data/mission_api.dart';
import 'package:nexus_flutter/features/missions/domain/mission_event.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';
import 'package:nexus_flutter/features/missions/presentation/missions_screen.dart';
import 'package:nexus_flutter/theme/nexus_theme.dart';

void main() {
  testWidgets('shows approval controls and submits approval', (tester) async {
    final api = _ApprovalMissionApi();
    final container = ProviderContainer(
      overrides: [missionApiProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    await container
        .read(missionControllerProvider.notifier)
        .start('Create an external task');

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          theme: NexusTheme.dark,
          home: const Scaffold(body: MissionsScreen()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Approval required'), findsOneWidget);
    expect(find.text('Approve'), findsOneWidget);
    expect(find.text('Reject'), findsOneWidget);

    await tester.tap(find.text('Approve'));
    await tester.pumpAndSettle();

    expect(api.approvals, 1);
  });
}

class _ApprovalMissionApi implements MissionApi {
  var approvals = 0;

  MissionRun get _waiting => const MissionRun(
    id: 'run_approval',
    goal: 'Create an external task',
    status: MissionRunStatus.waitingForApproval,
    steps: [
      MissionStep(
        title: 'Create task',
        tool: 'create_task',
        requiresApproval: true,
      ),
    ],
    traceCount: 6,
  );

  @override
  Future<MissionRun> startMission(String goal) async => _waiting;

  @override
  Stream<MissionEvent> watchMission(String runId, {int after = 0}) {
    return const Stream.empty();
  }

  @override
  Future<MissionRun> approve(String runId) async {
    approvals += 1;
    return _waiting.copyWith(status: MissionRunStatus.executing);
  }

  @override
  Future<MissionRun> cancel(String runId) async {
    return _waiting.copyWith(status: MissionRunStatus.cancelled);
  }

  @override
  Future<MissionRun> reject(String runId) async {
    return _waiting.copyWith(status: MissionRunStatus.replanning);
  }
}
