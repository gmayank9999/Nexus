import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/core/networking/api_client.dart';
import 'package:nexus_flutter/features/code/data/code_api.dart';

const maxArchiveBytes = 5 * 1024 * 1024;
typedef PickedArchive = ({String name, Uint8List bytes});

final archivePickerProvider = Provider<Future<PickedArchive?> Function()>(
  (ref) => () async {
    final file = await openFile(
      acceptedTypeGroups: const [
        XTypeGroup(
          label: 'ZIP repositories',
          extensions: ['zip'],
          uniformTypeIdentifiers: ['public.zip-archive'],
        ),
      ],
    );
    if (file == null) return null;
    return readRepositoryArchive(file);
  },
);

Future<PickedArchive> readRepositoryArchive(XFile file) async {
  final length = await file.length();
  if (length > maxArchiveBytes) {
    throw const FormatException('Archive exceeds 5 MiB.');
  }
  final builder = BytesBuilder(copy: false);
  await for (final chunk in file.openRead(0, length)) {
    builder.add(chunk);
    if (builder.length > maxArchiveBytes) {
      throw const FormatException('Archive exceeds 5 MiB.');
    }
  }
  final bytes = builder.takeBytes();
  return (name: file.name, bytes: bytes);
}

final codeApiProvider = Provider<CodeApi>(
  (ref) => DioCodeApi(ref.watch(dioProvider)),
);
final repositoriesProvider = FutureProvider.autoDispose(
  (ref) => ref.watch(codeApiProvider).list(),
);
final repositoryFilesProvider = FutureProvider.autoDispose
    .family<FileIndex, String>(
      (ref, id) => ref.watch(codeApiProvider).files(id),
    );
typedef SearchRequest = ({String id, String query});
typedef FlowRequest = ({String id, String path, String symbol});
typedef RootedFlowRequest = ({FlowRequest entry, String root});
final codeFlowProvider = FutureProvider.autoDispose
    .family<CodeFlow, RootedFlowRequest>(
      (ref, request) => ref
          .watch(codeApiProvider)
          .flow(
            request.entry.id,
            request.entry.path,
            request.entry.symbol,
            sourceRoot: request.root,
          ),
    );
final codeCallsProvider = FutureProvider.autoDispose.family<CallIndex, String>(
  (ref, id) => ref.watch(codeApiProvider).calls(id),
);
typedef DependencyRequest = ({String id, String root});
final codeDependenciesProvider = FutureProvider.autoDispose
    .family<ImportGraph, DependencyRequest>(
      (ref, request) =>
          ref.watch(codeApiProvider).dependencies(request.id, request.root),
    );
final codeSearchProvider = FutureProvider.autoDispose
    .family<SearchResult, SearchRequest>(
      (ref, request) =>
          ref.watch(codeApiProvider).search(request.id, request.query),
    );
typedef SourceRequest = ({String id, String path, int line});
final codeSourceProvider = FutureProvider.autoDispose
    .family<SourceWindow, SourceRequest>(
      (ref, request) => ref
          .watch(codeApiProvider)
          .read(request.id, request.path, request.line),
    );
