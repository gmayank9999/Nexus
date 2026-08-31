import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';

void main() {
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
}
