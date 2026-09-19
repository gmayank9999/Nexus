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
  int _generation = 0;

  @override
  MissionFeedState build() {
    ref.onDispose(() {
      _generation++;
      unawaited(_subscription?.cancel());
    });
    return const MissionFeedState();
  }

  Future<bool> start(String goal, {String? parentRunId}) async {
    final normalized = goal.trim();
    if (normalized.isEmpty || state.run?.isLoading == true) {
      return false;
    }
    return _load(
      () => ref
          .read(missionApiProvider)
          .startMission(normalized, parentRunId: parentRunId),
    );
  }

  Future<void> open(String runId) async {
    await _load(() => ref.read(missionApiProvider).getMission(runId));
  }

  Future<bool> _load(Future<MissionRun> Function() load) async {
    final generation = ++_generation;
    unawaited(_subscription?.cancel());
    state = const MissionFeedState(run: AsyncLoading());
    try {
      final run = await load();
      if (generation != _generation) return false;
      state = MissionFeedState(run: AsyncData(run), events: run.events);
      if (!run.isTerminal) {
        _subscription = ref
            .read(missionApiProvider)
            .watchMission(run.id, after: run.traceCount)
            .listen(
              (event) {
                if (generation == _generation) _receiveEvent(event);
              },
              onError: (Object error, StackTrace trace) {
                if (generation == _generation) {
                  _receiveStreamError(error, trace);
                }
              },
            );
      }
      return true;
    } catch (error, stackTrace) {
      if (generation != _generation) return false;
      state = MissionFeedState(run: AsyncError(error, stackTrace));
      return false;
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
    final generation = _generation;
    try {
      final run = await action(ref.read(missionApiProvider), current.value.id);
      if (generation != _generation) return;
      final latest = state.run;
      state = state.copyWith(
        run:
            latest is AsyncData<MissionRun> &&
                latest.value.traceCount > run.traceCount
            ? latest
            : AsyncData(run),
        actionPending: false,
      );
    } catch (error) {
      if (generation != _generation) return;
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
    if (event.runId != current.value.id) return;
    if (state.events.any((existing) => existing.sequence == event.sequence)) {
      return;
    }
    state = state.copyWith(
      run: AsyncData(
        event.sequence > current.value.traceCount
            ? current.value.applyEvent(event)
            : current.value,
      ),
      events: [...state.events, event]
        ..sort((left, right) => left.sequence.compareTo(right.sequence)),
      clearStreamError: true,
    );
  }

  void _receiveStreamError(Object error, StackTrace stackTrace) {
    state = state.copyWith(streamError: error.toString());
  }
}
