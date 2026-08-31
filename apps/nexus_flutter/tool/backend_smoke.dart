import 'dart:io';

import 'package:dio/dio.dart';
import 'package:nexus_flutter/features/system_status/data/health_api.dart';
import 'package:nexus_flutter/features/system_status/domain/system_health.dart';

Future<void> main(List<String> arguments) async {
  final baseUrl = arguments.isEmpty ? 'http://localhost:8000' : arguments.first;
  final api = DioHealthApi(Dio(BaseOptions(baseUrl: baseUrl)));
  final health = await api.fetchSystemHealth();
  final allOnline = [
    health.api,
    health.postgres,
    health.redis,
  ].every((state) => state == ServiceState.online);

  if (!allOnline) {
    stderr.writeln('NEXUS backend is reachable but not ready at $baseUrl.');
    exitCode = 1;
    return;
  }

  stdout.writeln('NEXUS API v${health.version} is ready at $baseUrl.');
}
