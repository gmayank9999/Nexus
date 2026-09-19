import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/missions/application/mission_controller.dart';
import 'package:nexus_flutter/features/missions/data/mission_api.dart';
import 'package:nexus_flutter/features/missions/domain/mission_event.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';

void main() {
  test(
    'opening completed history avoids a socket and restores the trace',
    () async {
      final api = _HistoryApi();
      final container = ProviderContainer(
        overrides: [missionApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);
      await container.read(missionControllerProvider.notifier).open('finished');
      final state = container.read(missionControllerProvider);
      expect(state.events.single.type, 'run_completed');
      expect(api.connections, 0);
    },
  );

  test(
    'resumes after snapshot cursor without applying duplicate progress',
    () async {
      final api = _HistoryApi();
      final container = ProviderContainer(
        overrides: [missionApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);
      addTearDown(api.events.close);
      await container.read(missionControllerProvider.notifier).open('active');
      expect(api.cursor, 7);
      api.events.add(_event('active', 7, 'tool_completed'));
      api.events.add(_event('other', 8, 'tool_completed'));
      api.events.add(_event('active', 8, 'tool_completed'));
      await Future<void>.delayed(Duration.zero);
      final run = container.read(missionControllerProvider).run!.requireValue;
      expect(run.currentStep, 2);
      expect(run.traceCount, 8);
    },
  );

  test('late historical response cannot replace a newer selection', () async {
    final api = _HistoryApi();
    final container = ProviderContainer(
      overrides: [missionApiProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    final controller = container.read(missionControllerProvider.notifier);
    final slow = controller.open('slow');
    await controller.open('finished');
    api.slow.complete(_run('slow'));
    await slow;
    expect(
      container.read(missionControllerProvider).run!.requireValue.id,
      'finished',
    );
  });
}

MissionEvent _event(String runId, int sequence, String type) => MissionEvent(
  id: 'evt_$sequence',
  runId: runId,
  sequence: sequence,
  type: type,
  timestamp: DateTime.utc(2026),
  payload: const {},
);

MissionRun _run(String id) => MissionRun(
  id: id,
  goal: 'Study architecture',
  status: id == 'active'
      ? MissionRunStatus.executing
      : MissionRunStatus.completed,
  steps: const [],
  traceCount: 7,
  currentStep: 1,
  events: id == 'active' ? const [] : [_event(id, 7, 'run_completed')],
);

class _HistoryApi implements MissionApi {
  final events = StreamController<MissionEvent>();
  final slow = Completer<MissionRun>();
  int connections = 0;
  int? cursor;
  @override
  Future<MissionRun> getMission(String runId) async =>
      runId == 'slow' ? slow.future : _run(runId);
  @override
  Future<List<MissionRun>> listMissions() async => [_run('finished')];
  @override
  Future<MissionRun> startMission(String goal, {String? parentRunId}) =>
      getMission('active');
  @override
  Stream<MissionEvent> watchMission(String runId, {int after = 0}) {
    connections++;
    cursor = after;
    return events.stream;
  }

  @override
  Future<MissionRun> approve(String runId) => getMission(runId);
  @override
  Future<MissionRun> reject(String runId) => getMission(runId);
  @override
  Future<MissionRun> cancel(String runId) => getMission(runId);
}
