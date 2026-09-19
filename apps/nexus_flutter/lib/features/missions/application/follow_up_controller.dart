import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';

final followUpProvider = NotifierProvider<FollowUpController, MissionRun?>(
  FollowUpController.new,
);

// Selecting context only prepares a draft; it never starts a mission.
class FollowUpController extends Notifier<MissionRun?> {
  @override
  MissionRun? build() => null;

  void select(MissionRun run) {
    if (run.canFollowUp) state = run;
  }

  void clear() => state = null;

  void consume(MissionRun? selection) {
    if (identical(state, selection)) clear();
  }
}
