import 'package:dio/dio.dart';
import 'package:nexus_flutter/features/missions/data/mission_event_stream.dart';
import 'package:nexus_flutter/features/missions/domain/mission_event.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';

abstract interface class MissionApi {
  Future<List<MissionRun>> listMissions();

  Future<MissionRun> getMission(String runId);

  Future<MissionRun> startMission(String goal);

  Stream<MissionEvent> watchMission(String runId, {int after = 0});

  Future<MissionRun> approve(String runId);

  Future<MissionRun> reject(String runId);

  Future<MissionRun> cancel(String runId);
}

class DioMissionApi implements MissionApi {
  const DioMissionApi(
    this._dio, [
    this._eventStream = const ReconnectingMissionEventStream(),
  ]);

  final Dio _dio;
  final ReconnectingMissionEventStream _eventStream;

  @override
  Future<List<MissionRun>> listMissions() async {
    final response = await _dio.get<List<dynamic>>('/api/v1/runs');
    return (response.data ?? [])
        .map(
          (value) =>
              MissionRun.fromJson(Map<String, dynamic>.from(value as Map)),
        )
        .toList(growable: false);
  }

  @override
  Future<MissionRun> getMission(String runId) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/runs/$runId',
    );
    return MissionRun.fromJson(response.data!);
  }

  @override
  Future<MissionRun> startMission(String goal) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/runs',
      data: {'goal': goal, 'user_id': 'local'},
    );
    final data = response.data;
    if (data == null) {
      throw const FormatException('The backend returned an empty mission.');
    }
    return MissionRun.fromJson(data);
  }

  @override
  Stream<MissionEvent> watchMission(String runId, {int after = 0}) {
    return _eventStream.watch(runId, after: after);
  }

  @override
  Future<MissionRun> approve(String runId) => _runAction(runId, 'approve');

  @override
  Future<MissionRun> reject(String runId) => _runAction(runId, 'reject');

  @override
  Future<MissionRun> cancel(String runId) => _runAction(runId, 'cancel');

  Future<MissionRun> _runAction(String runId, String action) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/runs/$runId/$action',
    );
    final data = response.data;
    if (data == null) {
      throw const FormatException('The backend returned an empty mission.');
    }
    return MissionRun.fromJson(data);
  }
}
