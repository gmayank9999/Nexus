import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/memory/application/memory_controller.dart';
import 'package:nexus_flutter/features/memory/data/memory_api.dart';
import 'package:nexus_flutter/features/memory/domain/nexus_memory.dart';
import 'package:nexus_flutter/features/memory/presentation/memory_screen.dart';

void main() {
  Future<void> mount(WidgetTester tester, _Api api) async {
    await tester.binding.setSurfaceSize(const Size(900, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [memoryApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: Scaffold(body: MemoryScreen())),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('edit is explicit, trims content and reloads confirmed memory', (
    tester,
  ) async {
    final api = _Api();
    await mount(tester, api);
    await tester.tap(find.byTooltip('Edit memory'));
    await tester.pumpAndSettle();
    expect(api.edits, isEmpty);
    await tester.enterText(find.byType(TextField), '  Detailed examples  ');
    await tester.tap(find.text('Save memory'));
    await tester.pumpAndSettle();
    expect(api.edits, ['Detailed examples']);
    expect(find.text('Detailed examples'), findsOneWidget);
    expect(find.text('100%'), findsOneWidget);
    expect(find.text('user'), findsOneWidget);
  });

  testWidgets('cancel and blank edits never call the API', (tester) async {
    final api = _Api();
    await mount(tester, api);
    await tester.tap(find.byTooltip('Edit memory'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '   ');
    await tester.tap(find.text('Save memory'));
    await tester.pumpAndSettle();
    expect(find.text('Enter 1 to 500 characters.'), findsOneWidget);
    expect(api.edits, isEmpty);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(find.text('Short examples'), findsOneWidget);
  });

  testWidgets('save failure keeps the draft for retry without raw errors', (
    tester,
  ) async {
    final api = _Api()..fail = true;
    await mount(tester, api);
    await tester.tap(find.byTooltip('Edit memory'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Keep this draft');
    await tester.tap(find.text('Save memory'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Could not save'), findsOneWidget);
    expect(find.textContaining('secret-server-error'), findsNothing);
    expect(
      tester.widget<TextField>(find.byType(TextField)).controller!.text,
      'Keep this draft',
    );
    api.fail = false;
    await tester.tap(find.text('Save memory'));
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsNothing);
    expect(find.text('Keep this draft'), findsOneWidget);
  });

  testWidgets('pending writes cannot be submitted twice or cancelled', (
    tester,
  ) async {
    final api = _Api()..pending = Completer<void>();
    await mount(tester, api);
    await tester.tap(find.byTooltip('Edit memory'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save memory'));
    await tester.pump();
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, 'Saving...'))
          .onPressed,
      isNull,
    );
    expect(
      tester
          .widget<TextButton>(find.widgetWithText(TextButton, 'Cancel'))
          .onPressed,
      isNull,
    );
    expect(api.edits, hasLength(1));
    api.pending!.complete();
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsNothing);
  });

  testWidgets('forget requires confirmation and handles a failed delete', (
    tester,
  ) async {
    final api = _Api();
    await mount(tester, api);
    await tester.tap(find.byTooltip('Forget'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(api.deletes, 0);
    api.fail = true;
    await tester.tap(find.byTooltip('Forget'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Forget'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Could not save'), findsOneWidget);
    api.fail = false;
    await tester.tap(find.widgetWithText(FilledButton, 'Forget'));
    await tester.pumpAndSettle();
    expect(find.text('No memories yet.'), findsOneWidget);
  });
}

NexusMemory _memory(String content, {bool confirmed = false}) => NexusMemory(
  id: 'memory_1',
  category: MemoryCategory.userPreference,
  content: content,
  confidence: confirmed ? 1 : 0.8,
  source: confirmed ? 'user' : 'agent',
  createdAt: '2026-09-19T00:00:00Z',
);

class _Api implements MemoryApi {
  List<NexusMemory> memories = [_memory('Short examples')];
  final edits = <String>[];
  int deletes = 0;
  bool fail = false;
  Completer<void>? pending;

  @override
  Future<List<NexusMemory>> listMemories() async => List.of(memories);

  @override
  Future<NexusMemory> editMemory(String id, String content) async {
    edits.add(content);
    await pending?.future;
    if (fail) throw StateError('secret-server-error');
    final edited = _memory(content, confirmed: true);
    memories = [edited];
    return edited;
  }

  @override
  Future<void> deleteMemory(String id) async {
    deletes++;
    if (fail) throw StateError('secret-server-error');
    memories = [];
  }
}
