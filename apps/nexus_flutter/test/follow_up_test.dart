import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/missions/application/follow_up_controller.dart';
import 'package:nexus_flutter/features/missions/data/mission_api.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';

void main() {
  test(
    'selection requires a completed reply and old submissions cannot clear newer drafts',
    () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final controller = container.read(followUpProvider.notifier);
      const parent = MissionRun(
        id: 'parent',
        goal: 'Earlier',
        status: MissionRunStatus.completed,
        steps: [],
        traceCount: 0,
        finalResponse: 'Reply',
      );
      controller.select(parent.copyWith(status: MissionRunStatus.executing));
      expect(container.read(followUpProvider), isNull);
      controller.select(parent.copyWith(finalResponse: ' '));
      expect(container.read(followUpProvider), isNull);
      controller.select(parent);
      expect(container.read(followUpProvider), same(parent));
      final newer = parent.copyWith(finalResponse: 'New reply');
      controller.select(newer);
      controller.consume(parent);
      expect(container.read(followUpProvider), same(newer));
      controller.consume(newer);
      expect(container.read(followUpProvider), isNull);
    },
  );

  test(
    'API sends only explicitly selected parent IDs, not client history',
    () async {
      final dio = Dio();
      addTearDown(dio.close);
      final bodies = <Map<String, dynamic>>[];
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (options, handler) {
            final body = Map<String, dynamic>.from(options.data as Map);
            bodies.add(body);
            handler.resolve(
              Response(
                requestOptions: options,
                statusCode: 201,
                data: {
                  'id': 'child',
                  'goal': body['goal'],
                  'status': 'created',
                  'parent_run_id': body['parent_run_id'],
                },
              ),
            );
          },
        ),
      );
      final api = DioMissionApi(dio);
      final child = await api.startMission('Follow up', parentRunId: 'parent');
      await api.startMission('Independent');
      expect(child.parentRunId, 'parent');
      expect(bodies, [
        {'goal': 'Follow up', 'user_id': 'local', 'parent_run_id': 'parent'},
        {'goal': 'Independent', 'user_id': 'local'},
      ]);
    },
  );
}
