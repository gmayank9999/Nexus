enum ServiceState { online, offline }

class SystemHealth {
  const SystemHealth({
    required this.api,
    required this.postgres,
    required this.redis,
    required this.version,
  });

  factory SystemHealth.fromJson({
    required Map<String, dynamic> health,
    required Map<String, dynamic> readiness,
  }) {
    final components = readiness['components'] as Map<String, dynamic>? ?? {};
    return SystemHealth(
      api: health['status'] == 'ok'
          ? ServiceState.online
          : ServiceState.offline,
      postgres: _componentState(components['postgres']),
      redis: _componentState(components['redis']),
      version: health['version'] as String? ?? 'unknown',
    );
  }

  final ServiceState api;
  final ServiceState postgres;
  final ServiceState redis;
  final String version;

  static ServiceState _componentState(Object? value) {
    if (value is Map<String, dynamic> && value['status'] == 'up') {
      return ServiceState.online;
    }
    return ServiceState.offline;
  }
}
