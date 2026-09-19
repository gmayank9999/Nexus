import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/outputs/data/outputs_api.dart';
import 'package:nexus_flutter/features/outputs/presentation/outputs_screen.dart';

void main() {
  testWidgets('task toggle persists completion before refreshing', (
    tester,
  ) async {
    final api = _OutputsApi();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [outputsApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: OutputsScreen(showTasks: true)),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byType(Checkbox));
    await tester.pumpAndSettle();
    expect(api.completed, isTrue);
    expect(tester.widget<Checkbox>(find.byType(Checkbox)).value, isTrue);
  });

  testWidgets('artifact expands to show saved content', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [outputsApiProvider.overrideWithValue(_OutputsApi())],
        child: const MaterialApp(home: OutputsScreen(showTasks: false)),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Architecture guide'));
    await tester.pumpAndSettle();
    expect(find.text('Review repository boundaries.'), findsOneWidget);
  });
}

class _OutputsApi extends OutputsApi {
  _OutputsApi() : super(Dio());
  bool completed = false;
  @override
  Future<List<MissionTask>> tasks(String? runId) async => [
    MissionTask(
      id: 't1',
      runId: 'r1',
      title: 'Review architecture',
      completed: completed,
    ),
  ];
  @override
  Future<void> setCompleted(String taskId, bool value) async {
    completed = value;
  }

  @override
  Future<List<MissionArtifact>> artifacts(String? runId) async => [
    const MissionArtifact(
      id: 'a1',
      runId: 'r1',
      type: 'study_guide',
      title: 'Architecture guide',
      content: 'Review repository boundaries.',
    ),
  ];
}
