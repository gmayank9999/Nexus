import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/core/networking/api_client.dart';
import 'package:nexus_flutter/features/missions/data/mission_api.dart';
import 'package:nexus_flutter/features/missions/domain/mission_event.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';

final missionApiProvider = Provider<MissionApi>(
  (ref) => DioMissionApi(ref.watch(dioProvider)),
);

final missionControllerProvider =
    NotifierProvider<MissionController, MissionFeedState>(
      MissionController.new,
    );

class MissionFeedState {
  const MissionFeedState({
    this.run,
    this.events = const [],
    this.actionPending = false,
    this.streamError,
  });

  final AsyncValue<MissionRun>? run;
  final List<MissionEvent> events;
  final bool actionPending;
  final String? streamError;

  MissionFeedState copyWith({
    AsyncValue<MissionRun>? run,
    List<MissionEvent>? events,
    bool? actionPending,
    String? streamError,
    bool clearStreamError = false,
  }) {
    return MissionFeedState(
      run: run ?? this.run,
      events: events ?? this.events,
      actionPending: actionPending ?? this.actionPending,
      streamError: clearStreamError ? null : streamError ?? this.streamError,
    );
  }
}

class MissionController extends Notifier<MissionFeedState> {
  StreamSubscription<MissionEvent>? _subscription;

  @override
  MissionFeedState build() {
    ref.onDispose(() => unawaited(_subscription?.cancel()));
    return const MissionFeedState();
  }

  Future<void> start(String goal) async {
    final normalized = goal.trim();
    if (normalized.isEmpty || state.run?.isLoading == true) {
      return;
    }
    await _subscription?.cancel();
    state = const MissionFeedState(run: AsyncLoading());
    try {
      final run = await ref.read(missionApiProvider).startMission(normalized);
      state = MissionFeedState(run: AsyncData(run));
      _subscription = ref
          .read(missionApiProvider)
          .watchMission(run.id)
          .listen(_receiveEvent, onError: _receiveStreamError);
    } catch (error, stackTrace) {
      state = MissionFeedState(run: AsyncError(error, stackTrace));
    }
  }

  Future<void> approve() => _performAction((api, runId) => api.approve(runId));

  Future<void> reject() => _performAction((api, runId) => api.reject(runId));

  Future<void> cancel() => _performAction((api, runId) => api.cancel(runId));

  Future<void> _performAction(
    Future<MissionRun> Function(MissionApi api, String runId) action,
  ) async {
    final current = state.run;
    if (current is! AsyncData<MissionRun> || state.actionPending) {
      return;
    }
    state = state.copyWith(actionPending: true, clearStreamError: true);
    try {
      final run = await action(ref.read(missionApiProvider), current.value.id);
      state = state.copyWith(run: AsyncData(run), actionPending: false);
    } catch (error) {
      state = state.copyWith(
        actionPending: false,
        streamError: error.toString(),
      );
    }
  }

  void _receiveEvent(MissionEvent event) {
    final current = state.run;
    if (current is! AsyncData<MissionRun>) {
      return;
    }
    if (state.events.any((existing) => existing.sequence == event.sequence)) {
      return;
    }
    state = state.copyWith(
      run: AsyncData(current.value.applyEvent(event)),
      events: [...state.events, event]
        ..sort((left, right) => left.sequence.compareTo(right.sequence)),
      clearStreamError: true,
    );
  }

  void _receiveStreamError(Object error, StackTrace stackTrace) {
    state = state.copyWith(streamError: error.toString());
  }
}
