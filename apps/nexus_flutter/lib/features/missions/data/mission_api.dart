import 'package:dio/dio.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';

abstract interface class MissionApi {
  Future<MissionRun> startMission(String goal);
}

class DioMissionApi implements MissionApi {
  const DioMissionApi(this._dio);

  final Dio _dio;

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
}
