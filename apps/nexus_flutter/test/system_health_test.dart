import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/system_status/domain/system_health.dart';

void main() {
  test('parses backend and dependency health independently', () {
    final health = SystemHealth.fromJson(
      health: const {'status': 'ok', 'version': '0.1.0'},
      readiness: const {
        'status': 'not_ready',
        'components': {
          'postgres': {'status': 'up'},
          'redis': {'status': 'down'},
        },
      },
    );

    expect(health.api, ServiceState.online);
    expect(health.postgres, ServiceState.online);
    expect(health.redis, ServiceState.offline);
    expect(health.version, '0.1.0');
  });
}
