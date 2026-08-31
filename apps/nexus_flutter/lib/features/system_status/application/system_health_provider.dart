import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/system_status/data/health_api.dart';
import 'package:nexus_flutter/features/system_status/domain/system_health.dart';

final systemHealthProvider = FutureProvider.autoDispose<SystemHealth>(
  (ref) => ref.watch(healthApiProvider).fetchSystemHealth(),
);
