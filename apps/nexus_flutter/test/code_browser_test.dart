import 'dart:async';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/code/application/code_providers.dart';
import 'package:nexus_flutter/features/code/data/code_api.dart';
import 'package:nexus_flutter/features/code/presentation/repositories_screen.dart';
import 'package:nexus_flutter/features/code/presentation/repository_screen.dart';
import 'package:nexus_flutter/features/code/presentation/upload_repository_dialog.dart';

void main() {
  testWidgets('function flow shows candidate graph and source navigation', (
    tester,
  ) async {
    final api = _Api();
    await tester.binding.setSurfaceSize(const Size(1100, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [codeApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: RepositoryScreen(id: 'repo_1')),
      ),
    );
    await tester.pumpAndSettle();
    expect(api.lastFlow, isNull);
    await tester.tap(find.text('app.py'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Inspect flow for App.login'));
    await tester.pumpAndSettle();
    expect(api.lastFlow, (id: 'repo_1', path: 'app.py', symbol: 'App.login'));
    expect(find.textContaining('Candidate → verify'), findsOneWidget);
    expect(find.textContaining('Graph limited:'), findsOneWidget);
    expect(find.textContaining('Index incomplete.'), findsOneWidget);
    await tester.tap(find.byTooltip('Read candidate declaration'));
    await tester.pumpAndSettle();
    expect(api.lastRead, (id: 'repo_1', path: 'app.py', line: 12));
    await tester.tap(find.text('Close'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('verify — line 8'));
    await tester.pumpAndSettle();
    expect(api.lastRead, (id: 'repo_1', path: 'app.py', line: 8));
  });

  testWidgets('flow errors retry without disclosing server details', (
    tester,
  ) async {
    final api = _Api()..failFlow = true;
    await tester.binding.setSurfaceSize(const Size(1000, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [codeApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: RepositoryScreen(id: 'repo_1')),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('app.py'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Inspect flow for App.login'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Could not inspect flow.'), findsOneWidget);
    expect(find.textContaining('private-flow-error'), findsNothing);
    api.failFlow = false;
    await tester.tap(find.text('Retry flow'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Candidate → verify'), findsOneWidget);
  });
  testWidgets('call sites load explicitly and open cited source', (
    tester,
  ) async {
    final api = _Api();
    await tester.binding.setSurfaceSize(const Size(1000, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [codeApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: RepositoryScreen(id: 'repo_1')),
      ),
    );
    await tester.pumpAndSettle();
    expect(api.callLoads, 0);
    await tester.tap(find.text('Python call sites'));
    await tester.pumpAndSettle();
    expect(api.callLoads, 0);
    await tester.tap(find.text('Load call sites'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Call index is incomplete.'), findsOneWidget);
    expect(find.textContaining('Call results are capped'), findsOneWidget);
    expect(
      find.textContaining('Dynamic expression: unresolved'),
      findsOneWidget,
    );
    expect(
      find.textContaining('Scope or callee label truncated'),
      findsOneWidget,
    );
    await tester.tap(find.text('app.py:4 calls <dynamic expression>'));
    await tester.pumpAndSettle();
    expect(api.lastRead, (id: 'repo_1', path: 'app.py', line: 4));
  });

  testWidgets('call-site failure retries and empty indexes stay qualified', (
    tester,
  ) async {
    final api = _Api()..failCalls = true;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [codeApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: RepositoryScreen(id: 'repo_1')),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Python call sites'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Load call sites'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Could not load call sites.'), findsOneWidget);
    expect(find.textContaining('private-call-error'), findsNothing);
    api.failCalls = false;
    api.emptyCalls = true;
    await tester.tap(find.text('Load call sites'));
    await tester.pumpAndSettle();
    expect(
      find.textContaining('This does not prove there are no calls.'),
      findsOneWidget,
    );
    expect(api.callLoads, 2);
  });
  testWidgets('dependency scope, warnings and source navigation', (
    tester,
  ) async {
    final api = _Api();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [codeApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: RepositoryScreen(id: 'repo_1')),
      ),
    );
    await tester.pumpAndSettle();
    expect(api.lastRoot, isNull);
    await tester.tap(find.text('Python import dependencies'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextField, 'Snapshot source root'),
      'src',
    );
    await tester.tap(find.text('Load dependencies'));
    await tester.pumpAndSettle();
    expect(api.lastRoot, 'src');
    expect(find.text('Source index is incomplete.'), findsOneWidget);
    expect(find.text('Only the first 500 imports are shown.'), findsOneWidget);
    await tester.tap(find.text('app.py:3 imports helper'));
    await tester.pumpAndSettle();
    expect(api.lastRead, (id: 'repo_1', path: 'app.py', line: 3));
    await tester.tap(find.text('Close'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Read imported module'));
    await tester.pumpAndSettle();
    expect(api.lastRead, (id: 'repo_1', path: 'helper.py', line: 1));
  });

  testWidgets('dependency failure can retry without exposing server details', (
    tester,
  ) async {
    final api = _Api()..failGraph = true;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [codeApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: RepositoryScreen(id: 'repo_1')),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Python import dependencies'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Load dependencies'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Could not load dependencies.'), findsOneWidget);
    expect(find.textContaining('private-error'), findsNothing);
    api.failGraph = false;
    await tester.tap(find.text('Load dependencies'));
    await tester.pumpAndSettle();
    expect(find.text('app.py:3 imports helper'), findsOneWidget);
  });
  test(
    'archive reader handles data-backed files and rejects oversize',
    () async {
      final selected = await readRepositoryArchive(
        XFile.fromData(Uint8List.fromList([1, 2, 3]), name: 'sample.zip'),
      );
      expect(selected.bytes, [1, 2, 3]);
      await expectLater(
        readRepositoryArchive(
          XFile.fromData(Uint8List(maxArchiveBytes + 1), name: 'large.zip'),
        ),
        throwsFormatException,
      );
    },
  );
  Future<void> mount(
    WidgetTester tester,
    Widget screen,
    _Api api, {
    Future<PickedArchive?> Function()? picker,
  }) async {
    await tester.binding.setSurfaceSize(const Size(1000, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          codeApiProvider.overrideWithValue(api),
          archivePickerProvider.overrideWithValue(
            picker ??
                () async =>
                    (name: 'sample.zip', bytes: Uint8List.fromList([1, 2, 3])),
          ),
        ],
        child: MaterialApp(home: screen),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('ZIP selection requires a separate upload confirmation', (
    tester,
  ) async {
    final api = _Api();
    await mount(tester, const RepositoriesScreen(), api);
    await tester.tap(find.text('Import ZIP'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Choose ZIP'));
    await tester.pumpAndSettle();
    expect(api.uploads, 0);
    expect(find.text('sample.zip'), findsOneWidget);
    await tester.tap(find.text('Upload snapshot'));
    await tester.pumpAndSettle();
    expect(api.uploads, 1);
    expect(find.byType(UploadRepositoryDialog), findsNothing);
    expect(find.text('sample'), findsOneWidget);
  });

  testWidgets('cancelled or oversized selections do not upload', (
    tester,
  ) async {
    final api = _Api();
    var calls = 0;
    await mount(
      tester,
      const RepositoriesScreen(),
      api,
      picker: () async {
        if (calls++ == 0) return null;
        return (name: 'large.zip', bytes: Uint8List(maxArchiveBytes + 1));
      },
    );
    await tester.tap(find.text('Import ZIP'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Choose ZIP'));
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Upload snapshot'),
          )
          .onPressed,
      isNull,
    );
    await tester.tap(find.text('Choose ZIP'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Could not select'), findsOneWidget);
    expect(api.uploads, 0);
  });

  testWidgets('pending upload prevents duplicate submission', (tester) async {
    final api = _Api()..pendingUpload = Completer<void>();
    await mount(tester, const RepositoriesScreen(), api);
    await tester.tap(find.text('Import ZIP'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Choose ZIP'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Upload snapshot'));
    await tester.pump();
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, 'Working...'))
          .onPressed,
      isNull,
    );
    expect(api.uploads, 1);
    api.pendingUpload!.complete();
    await tester.pumpAndSettle();
    expect(find.byType(UploadRepositoryDialog), findsNothing);
  });

  testWidgets('failed imports retain the review and warn about duplicates', (
    tester,
  ) async {
    final api = _Api()..failUpload = true;
    await mount(tester, const RepositoriesScreen(), api);
    await tester.tap(find.text('Import ZIP'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Choose ZIP'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Upload snapshot'));
    await tester.pumpAndSettle();
    expect(
      find.textContaining('Refresh repositories before retrying'),
      findsOneWidget,
    );
    expect(find.text('sample.zip'), findsOneWidget);
    expect(find.textContaining('private-server-error'), findsNothing);
  });

  testWidgets('file symbols open source without executing markup', (
    tester,
  ) async {
    final api = _Api();
    await mount(tester, const RepositoryScreen(id: 'repo_1'), api);
    await tester.tap(find.text('app.py'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('App.login'));
    await tester.pumpAndSettle();
    expect(api.lastRead, (id: 'repo_1', path: 'app.py', line: 7));
    expect(find.text('7  <script>not executed</script>'), findsOneWidget);
    expect(find.textContaining('SHA-256:'), findsOneWidget);
  });

  testWidgets('search shows locations, empty results, and truncation', (
    tester,
  ) async {
    final api = _Api();
    await mount(tester, const RepositoryScreen(id: 'repo_1'), api);
    await tester.enterText(find.byType(TextField), 'login');
    await tester.tap(find.text('Search'));
    await tester.pumpAndSettle();
    expect(find.text('app.py:7'), findsOneWidget);
    expect(find.textContaining('Only the first 20'), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'empty');
    await tester.tap(find.text('Search'));
    await tester.pumpAndSettle();
    expect(find.text('No matching lines.'), findsOneWidget);
    expect(find.text('app.py:7'), findsNothing);
  });

  testWidgets('late search cannot replace a newer query', (tester) async {
    final api = _Api()..slow = Completer<SearchResult>();
    await mount(tester, const RepositoryScreen(id: 'repo_1'), api);
    await tester.enterText(find.byType(TextField), 'slow');
    await tester.tap(find.text('Search'));
    await tester.pump();
    await tester.enterText(find.byType(TextField), 'empty');
    await tester.tap(find.text('Search'));
    await tester.pumpAndSettle();
    api.slow!.complete((
      matches: [const CodeMatch('stale.py', 1, 'old')],
      truncated: false,
    ));
    await tester.pumpAndSettle();
    expect(find.text('No matching lines.'), findsOneWidget);
    expect(find.text('stale.py:1'), findsNothing);
  });

  test(
    'Dio sends query parameters and multipart data to repository routes',
    () async {
      final dio = Dio();
      addTearDown(dio.close);
      final requests = <RequestOptions>[];
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (request, handler) {
            requests.add(request);
            handler.resolve(
              Response(
                requestOptions: request,
                data: request.method == 'POST'
                    ? {'id': 'repo_1', 'name': 'Test', 'file_count': 1}
                    : {
                        'matches': <dynamic>[],
                        'edges': <dynamic>[],
                        'truncated': false,
                        'incomplete_index': true,
                        'calls': <dynamic>[],
                        'nodes': <dynamic>[],
                        'semantics': 'Candidate graph only',
                      },
              ),
            );
          },
        ),
      );
      final api = DioCodeApi(dio);
      await api.upload('Test', Uint8List.fromList([1]), CancelToken());
      await api.search('repo_1', 'a&b');
      final graph = await api.dependencies('repo_1', 'wrapper/src');
      expect(graph.edges, isEmpty);
      expect(graph.incomplete, isTrue);
      expect(requests[2].path, '/api/v1/repositories/repo_1/dependencies');
      expect(requests[2].queryParameters, {'source_root': 'wrapper/src'});
      final calls = await api.calls('repo_1');
      expect(requests[3].path, '/api/v1/repositories/repo_1/calls');
      expect(calls.calls, isEmpty);
      expect(calls.incomplete, isTrue);
      final flow = await api.flow('repo_1', 'src/app.py', 'App.login');
      expect(requests[4].path, '/api/v1/repositories/repo_1/flow');
      expect(requests[4].queryParameters, {
        'path': 'src/app.py',
        'symbol': 'App.login',
      });
      expect(flow.incomplete, isTrue);
      expect(flow.semantics, 'Candidate graph only');
      expect(requests[0].data, isA<FormData>());
      expect(requests[0].queryParameters, {'name': 'Test'});
      expect(requests[1].queryParameters, {'query': 'a&b'});
    },
  );
}

class _Api implements CodeApi {
  FlowRequest? lastFlow;
  bool failFlow = false;
  @override
  Future<CodeFlow> flow(String id, String path, String symbol) async {
    lastFlow = (id: id, path: path, symbol: symbol);
    if (failFlow) throw StateError('private-flow-error');
    return (
      nodes: [
        FlowNode.fromJson({
          'id': 'entry',
          'name': symbol,
          'path': path,
          'line': 7,
        }),
        FlowNode.fromJson({
          'id': 'target',
          'name': 'verify',
          'path': path,
          'line': 12,
        }),
      ],
      edges: [
        FlowEdge.fromJson({
          'source': 'entry',
          'target': 'target',
          'callee': 'verify',
          'line': 8,
          'resolution': 'same_file_name_candidate',
        }),
      ],
      truncated: true,
      incomplete: true,
      semantics: 'Names are not verified bindings.',
    );
  }

  int callLoads = 0;
  bool failCalls = false;
  bool emptyCalls = false;
  @override
  Future<CallIndex> calls(String id) async {
    callLoads++;
    if (failCalls) throw StateError('private-call-error');
    return (
      calls: emptyCalls
          ? <CallSite>[]
          : [
              CallSite.fromJson({
                'path': 'app.py',
                'line': 4,
                'scope': 'login',
                'callee': '<dynamic expression>',
                'dynamic': true,
                'label_truncated': true,
              }),
            ],
      truncated: !emptyCalls,
      incomplete: true,
    );
  }

  String? lastRoot;
  bool failGraph = false;
  @override
  Future<ImportGraph> dependencies(String id, String root) async {
    lastRoot = root;
    if (failGraph) throw StateError('private-error');
    return (
      edges: [
        ImportEdge.fromJson({
          'source': 'app.py',
          'line': 3,
          'module': 'helper',
          'target': 'helper.py',
          'resolution': 'local_declared_module',
        }),
      ],
      truncated: true,
      incomplete: true,
    );
  }

  int uploads = 0;
  bool failUpload = false;
  Completer<void>? pendingUpload;
  Completer<SearchResult>? slow;
  SourceRequest? lastRead;

  @override
  Future<List<RepositoryInfo>> list() async =>
      uploads == 0 ? [] : [const RepositoryInfo('repo_1', 'sample', 1)];
  @override
  Future<RepositoryInfo> upload(
    String name,
    Uint8List bytes,
    CancelToken cancel,
  ) async {
    uploads++;
    await pendingUpload?.future;
    if (failUpload) throw StateError('private-server-error');
    return RepositoryInfo('repo_1', name, 1);
  }

  @override
  Future<FileIndex> files(String id) async => (
    files: [
      const IndexedFile(
        'app.py',
        'python',
        [(name: 'App.login', line: 7)],
        false,
        false,
      ),
    ],
    skipped: 2,
  );
  @override
  Future<SearchResult> search(String id, String query) async {
    if (query == 'slow') return slow!.future;
    return (
      matches: query == 'empty'
          ? <CodeMatch>[]
          : [const CodeMatch('app.py', 7, 'login')],
      truncated: query != 'empty',
    );
  }

  @override
  Future<SourceWindow> read(String id, String path, int line) async {
    lastRead = (id: id, path: path, line: line);
    return (
      content: '<script>not executed</script>',
      hash: 'abc123',
      startLine: line,
      totalLines: 8,
      truncated: false,
    );
  }
}
