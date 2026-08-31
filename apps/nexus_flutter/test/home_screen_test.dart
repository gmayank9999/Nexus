import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/home/presentation/home_screen.dart';
import 'package:nexus_flutter/features/system_status/application/system_health_provider.dart';
import 'package:nexus_flutter/features/system_status/domain/system_health.dart';
import 'package:nexus_flutter/theme/nexus_theme.dart';

void main() {
  testWidgets('renders the command surface and live system state', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          systemHealthProvider.overrideWith(
            (ref) async => const SystemHealth(
              api: ServiceState.online,
              postgres: ServiceState.online,
              redis: ServiceState.online,
              version: '0.1.0',
            ),
          ),
        ],
        child: MaterialApp(
          theme: NexusTheme.dark,
          home: const Scaffold(body: HomeScreen()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('NEXUS'), findsOneWidget);
    expect(find.text('What do you want to accomplish?'), findsOneWidget);
    expect(find.text('API v0.1.0'), findsOneWidget);
    expect(find.text('Online'), findsNWidgets(2));
  });
}
