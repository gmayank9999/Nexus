import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/missions/domain/mission_event.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';

void main() {
  test('retains follow-up metadata through streamed updates', () {
    final run = MissionRun.fromJson(const {
      'id': 'run_child',
      'goal': 'Next',
      'status': 'created',
      'parent_run_id': 'run_parent',
      'context': {'conversation_truncated': true},
    });
    expect(run.parentRunId, 'run_parent');
    expect(run.contextTruncated, isTrue);
    expect(run.canFollowUp, isFalse);
    final updated = run.applyEvent(
      MissionEvent(
        id: 'event_1',
        runId: run.id,
        sequence: 1,
        type: 'run_completed',
        timestamp: DateTime.utc(2026),
        payload: const {'response': 'Done'},
      ),
    );
    expect(updated.parentRunId, run.parentRunId);
    expect(updated.contextTruncated, isTrue);
    expect(updated.canFollowUp, isTrue);
  });

  test('parses a completed mission snapshot', () {
    final mission = MissionRun.fromJson(const {
      'id': 'run_1',
      'goal': 'Create a task',
      'status': 'completed',
      'final_response': 'Created task: Learn Flutter.',
      'plan': {
        'steps': [
          {'title': 'Create task', 'tool': 'create_task'},
        ],
      },
      'trace': [
        {'type': 'run_created'},
        {'type': 'run_completed'},
      ],
      'error': null,
    });

    expect(mission.status, MissionRunStatus.completed);
    expect(mission.steps.single.tool, 'create_task');
    expect(mission.traceCount, 2);
  });

  test('applies ordered events to the mission snapshot', () {
    const mission = MissionRun(
      id: 'run_1',
      goal: 'Create a task',
      status: MissionRunStatus.created,
      steps: [],
      traceCount: 1,
    );
    final updated = mission
        .applyEvent(
          MissionEvent(
            id: 'evt_2',
            runId: 'run_1',
            sequence: 2,
            type: 'status_changed',
            timestamp: DateTime.utc(2026),
            payload: const {'to': 'planning'},
          ),
        )
        .applyEvent(
          MissionEvent(
            id: 'evt_3',
            runId: 'run_1',
            sequence: 3,
            type: 'run_completed',
            timestamp: DateTime.utc(2026),
            payload: const {'response': 'Done'},
          ),
        );

    expect(updated.status, MissionRunStatus.completed);
    expect(updated.finalResponse, 'Done');
    expect(updated.traceCount, 3);
  });
}
