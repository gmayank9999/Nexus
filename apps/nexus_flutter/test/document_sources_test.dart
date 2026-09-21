import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/knowledge/application/knowledge_controller.dart';
import 'package:nexus_flutter/features/knowledge/data/knowledge_api.dart';
import 'package:nexus_flutter/features/knowledge/presentation/document_citations.dart';
import 'package:nexus_flutter/features/knowledge/presentation/document_source_dialog.dart';
import 'package:nexus_flutter/features/missions/domain/mission_event.dart';

void main() {
  testWidgets('unavailable source retries without exposing server errors', (
    tester,
  ) async {
    final dio = Dio();
    addTearDown(dio.close);
    var failed = true;
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          if (failed) {
            handler.reject(
              DioException(
                requestOptions: options,
                message: 'private-server-error',
              ),
            );
          } else {
            handler.resolve(
              Response(
                requestOptions: options,
                data: {
                  'document_id': 'doc_1',
                  'title': 'Resume',
                  'chunk_id': 'chunk_0',
                  'chunk_index': 0,
                  'chunk_count': 1,
                  'text': 'Recovered source',
                  'page': null,
                  'section': null,
                  'truncated': false,
                },
              ),
            );
          }
        },
      ),
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          knowledgeApiProvider.overrideWithValue(DioKnowledgeApi(dio)),
        ],
        child: const MaterialApp(
          home: Scaffold(body: DocumentSourceDialog(id: 'doc_1')),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Source unavailable.'), findsOneWidget);
    expect(find.textContaining('private-server-error'), findsNothing);
    failed = false;
    await tester.tap(find.text('Retry source'));
    await tester.pumpAndSettle();
    expect(find.text('Recovered source'), findsOneWidget);
  });
  testWidgets(
    'retrieval citations open exact chunks as plain text and page through source',
    (tester) async {
      final dio = Dio();
      addTearDown(dio.close);
      final requests = <RequestOptions>[];
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (options, handler) {
            requests.add(options);
            final index = options.queryParameters['chunk_index'] as int;
            handler.resolve(
              Response(
                requestOptions: options,
                data: {
                  'document_id': 'doc_1',
                  'title': 'Resume',
                  'chunk_id': 'chunk_$index',
                  'chunk_index': index,
                  'chunk_count': 2,
                  'text': '<script>source $index</script>',
                  'page': null,
                  'section': null,
                  'truncated': true,
                },
              ),
            );
          },
        ),
      );
      final event = MissionEvent(
        id: 'event',
        runId: 'run',
        sequence: 1,
        type: 'tool_completed',
        timestamp: DateTime(2026),
        payload: {
          'tool': 'search_files',
          'output': {
            'matches': [
              {
                'document_id': 'doc_1',
                'chunk_id': 'chunk_0',
                'title': 'Resume',
              },
              {
                'document_id': 'doc_1',
                'chunk_id': 'chunk_0',
                'title': 'Resume',
              },
              {
                'document_id': '../bad',
                'chunk_id': 'chunk_0',
                'title': 'Invalid',
              },
            ],
          },
        },
      );
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            knowledgeApiProvider.overrideWithValue(DioKnowledgeApi(dio)),
          ],
          child: MaterialApp(
            home: Scaffold(body: DocumentCitations(events: [event])),
          ),
        ),
      );
      expect(find.text('Resume'), findsOneWidget);
      expect(find.text('Invalid'), findsNothing);
      expect(requests, isEmpty);
      await tester.tap(find.text('Resume'));
      await tester.pumpAndSettle();
      expect(requests.single.path, '/api/v1/documents/doc_1/source');
      expect(requests.single.queryParameters['chunk_id'], 'chunk_0');
      expect(find.text('<script>source 0</script>'), findsOneWidget);
      expect(find.text('Excerpt capped at 20,000 characters.'), findsOneWidget);
      await tester.tap(find.text('Next chunk'));
      await tester.pumpAndSettle();
      expect(requests.last.queryParameters, {'chunk_index': 1});
      expect(find.text('Chunk 2 of 2'), findsOneWidget);
      await tester.tap(find.text('Previous chunk'));
      await tester.pumpAndSettle();
      expect(requests.last.queryParameters, {'chunk_index': 0});
    },
  );
}
