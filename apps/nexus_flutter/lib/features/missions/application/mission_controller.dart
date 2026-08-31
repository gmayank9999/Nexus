import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/core/networking/api_client.dart';
import 'package:nexus_flutter/features/missions/data/mission_api.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';

final missionApiProvider = Provider<MissionApi>(
  (ref) => DioMissionApi(ref.watch(dioProvider)),
);

final missionControllerProvider =
    NotifierProvider<MissionController, AsyncValue<MissionRun>?>(
      MissionController.new,
    );

class MissionController extends Notifier<AsyncValue<MissionRun>?> {
  @override
  AsyncValue<MissionRun>? build() => null;

  Future<void> start(String goal) async {
    final normalized = goal.trim();
    if (normalized.isEmpty || state?.isLoading == true) {
      return;
    }
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => ref.read(missionApiProvider).startMission(normalized),
    );
  }
}
