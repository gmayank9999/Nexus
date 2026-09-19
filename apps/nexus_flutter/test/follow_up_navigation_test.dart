import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:nexus_flutter/features/missions/application/follow_up_controller.dart';
import 'package:nexus_flutter/features/missions/application/mission_controller.dart';
import 'package:nexus_flutter/features/missions/data/mission_api.dart';
import 'package:nexus_flutter/features/missions/domain/mission_event.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';
import 'package:nexus_flutter/features/missions/presentation/mission_detail_screen.dart';

void main() {
  testWidgets(
    'history links to the parent and prepares an explicit follow-up draft',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(900, 1200));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final api = _Api();
      final container = ProviderContainer(
        overrides: [missionApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);
      final router = GoRouter(
        initialLocation: '/missions/child',
        routes: [
          GoRoute(
            path: '/missions/:id',
            builder: (context, state) => Scaffold(
              body: MissionDetailScreen(runId: state.pathParameters['id']!),
            ),
          ),
          GoRoute(
            path: '/home',
            builder: (context, state) =>
                const Scaffold(body: Text('Compose your next goal')),
          ),
        ],
      );
      addTearDown(router.dispose);
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Earlier context was shortened'),
        findsOneWidget,
      );
      await tester.tap(find.text('View previous mission'));
      await tester.pumpAndSettle();
      expect(find.text('Goal parent'), findsOneWidget);
      expect(find.text('View previous mission'), findsNothing);
      await tester.tap(find.text('Follow up'));
      await tester.pumpAndSettle();
      expect(find.text('Compose your next goal'), findsOneWidget);
      expect(container.read(followUpProvider)?.id, 'parent');
      expect(api.submissions, 0);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}

class _Api implements MissionApi {
  int submissions = 0;

  @override
  Future<MissionRun> getMission(String runId) async => MissionRun(
    id: runId,
    goal: 'Goal $runId',
    status: MissionRunStatus.completed,
    steps: const [],
    traceCount: 0,
    finalResponse: 'Reply $runId',
    parentRunId: runId == 'child' ? 'parent' : null,
    contextTruncated: runId == 'child',
  );

  @override
  Future<List<MissionRun>> listMissions() async => [];
  @override
  Future<MissionRun> startMission(String goal, {String? parentRunId}) async {
    submissions++;
    return getMission('new');
  }

  @override
  Stream<MissionEvent> watchMission(String runId, {int after = 0}) =>
      const Stream.empty();
  @override
  Future<MissionRun> approve(String runId) => throw UnimplementedError();
  @override
  Future<MissionRun> reject(String runId) => throw UnimplementedError();
  @override
  Future<MissionRun> cancel(String runId) => throw UnimplementedError();
}
