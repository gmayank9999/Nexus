import 'dart:async';
import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/knowledge/application/document_picker.dart';
import 'package:nexus_flutter/features/knowledge/application/knowledge_controller.dart';
import 'package:nexus_flutter/features/knowledge/data/knowledge_api.dart';
import 'package:nexus_flutter/features/knowledge/domain/knowledge_document.dart';
import 'package:nexus_flutter/features/knowledge/presentation/knowledge_screen.dart';

const _doc = KnowledgeDocument(
  id: 'doc_1',
  title: 'resume.txt',
  status: DocumentStatus.pending,
  mimeType: 'text/plain',
  sizeBytes: 3,
  chunkCount: 0,
);

class _Api implements KnowledgeApi {
  @override
  Future<DocumentSource> readSource(
    String id, {
    String? chunkId,
    int index = 0,
  }) async => throw UnimplementedError();
  int uploads = 0;
  bool fail = false;
  Completer<void>? pending;
  @override
  Future<List<KnowledgeDocument>> listDocuments() async => [];
  @override
  Future<void> deleteDocument(String id) async {}
  @override
  Future<KnowledgeDocument> uploadDocument({
    required String filename,
    required List<int> bytes,
    required String mimeType,
  }) async {
    uploads++;
    await pending?.future;
    if (fail) throw StateError('private-error');
    return _doc;
  }
}

void main() {
  Future<void> mount(
    WidgetTester tester,
    _Api api, {
    Future<PickedDocument?> Function()? picker,
  }) async {
    await tester.binding.setSurfaceSize(const Size(1000, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          knowledgeApiProvider.overrideWithValue(api),
          documentPickerProvider.overrideWithValue(
            picker ??
                () async => (
                  name: 'resume.txt',
                  mime: 'text/plain',
                  bytes: Uint8List.fromList([1, 2, 3]),
                ),
          ),
        ],
        child: const MaterialApp(home: Scaffold(body: KnowledgeScreen())),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Upload'));
    await tester.pumpAndSettle();
  }

  testWidgets('selection is local and upload requires confirmation', (
    tester,
  ) async {
    final api = _Api();
    await mount(tester, api);
    await tester.tap(find.text('Choose document'));
    await tester.pumpAndSettle();
    expect(api.uploads, 0);
    expect(find.text('resume.txt'), findsOneWidget);
    await tester.tap(find.text('Upload selected document'));
    await tester.pumpAndSettle();
    expect(api.uploads, 1);
    expect(find.text('Upload document'), findsNothing);
    expect(find.text('resume.txt'), findsOneWidget);
    expect(find.text('Refresh documents'), findsOneWidget);
  });

  testWidgets('failed uploads retain selection and disclose possible commit', (
    tester,
  ) async {
    final api = _Api()..fail = true;
    await mount(tester, api);
    await tester.tap(find.text('Choose document'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Upload selected document'));
    await tester.pumpAndSettle();
    expect(find.text('resume.txt'), findsOneWidget);
    expect(find.textContaining('server may have accepted'), findsOneWidget);
    expect(find.textContaining('private-error'), findsNothing);
    expect(api.uploads, 1);
  });

  testWidgets('pending uploads prevent duplicate submissions', (tester) async {
    final api = _Api()..pending = Completer<void>();
    await mount(tester, api);
    await tester.tap(find.text('Choose document'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Upload selected document'));
    await tester.pump();
    await tester.tap(find.text('Upload selected document'));
    expect(api.uploads, 1);
    api.pending!.complete();
    await tester.pumpAndSettle();
  });

  testWidgets('cancelled picker does not enable upload', (tester) async {
    final api = _Api();
    await mount(tester, api, picker: () async => null);
    await tester.tap(find.text('Choose document'));
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Upload selected document'),
          )
          .onPressed,
      isNull,
    );
    expect(api.uploads, 0);
  });

  test(
    'picker reads supported bytes and rejects oversized or unsupported files',
    () async {
      final file = await readPickedDocument(
        XFile.fromData(
          Uint8List.fromList([1]),
          path: 'resume.TXT',
          name: 'resume.TXT',
        ),
      );
      expect(file.mime, 'text/plain');
      expect(file.bytes, [1]);
      await expectLater(
        readPickedDocument(
          XFile.fromData(Uint8List(1), path: 'bad.exe', name: 'bad.exe'),
        ),
        throwsFormatException,
      );
      await expectLater(
        readPickedDocument(
          XFile.fromData(
            Uint8List(maxDocumentBytes + 1),
            path: 'big.pdf',
            name: 'big.pdf',
          ),
        ),
        throwsFormatException,
      );
    },
  );
}
