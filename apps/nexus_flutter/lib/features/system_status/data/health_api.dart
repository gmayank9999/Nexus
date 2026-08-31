import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/core/networking/api_client.dart';
import 'package:nexus_flutter/features/system_status/domain/system_health.dart';

abstract interface class HealthApi {
  Future<SystemHealth> fetchSystemHealth();
}

class DioHealthApi implements HealthApi {
  const DioHealthApi(this._dio);

  final Dio _dio;

  @override
  Future<SystemHealth> fetchSystemHealth() async {
    final responses = await Future.wait([
      _dio.get<Map<String, dynamic>>('/health'),
      _dio.get<Map<String, dynamic>>(
        '/ready',
        options: Options(
          validateStatus: (status) => status != null && status < 600,
        ),
      ),
    ]);

    return SystemHealth.fromJson(
      health: responses[0].data ?? const {},
      readiness: responses[1].data ?? const {},
    );
  }
}

final healthApiProvider = Provider<HealthApi>(
  (ref) => DioHealthApi(ref.watch(dioProvider)),
);
