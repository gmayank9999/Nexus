import 'package:nexus_flutter/core/config/api_host_stub.dart'
    if (dart.library.io) 'package:nexus_flutter/core/config/api_host_io.dart';

abstract final class ApiConfig {
  static const _configuredBaseUrl = String.fromEnvironment(
    'NEXUS_API_BASE_URL',
  );

  static String get baseUrl => _configuredBaseUrl.isNotEmpty
      ? _configuredBaseUrl
      : 'http://${defaultApiHost()}:8000';
}
