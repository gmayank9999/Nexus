import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/core/networking/api_client.dart';
import 'package:nexus_flutter/features/system_status/data/health_api.dart';
import 'package:nexus_flutter/features/system_status/domain/system_health.dart';

final healthApiProvider = Provider<HealthApi>(
  (ref) => DioHealthApi(ref.watch(dioProvider)),
);

final systemHealthProvider = FutureProvider.autoDispose<SystemHealth>(
  (ref) => ref.watch(healthApiProvider).fetchSystemHealth(),
);
