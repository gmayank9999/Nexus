/// Riverpod state + controller for the knowledge base feature.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/core/networking/api_client.dart';
import 'package:nexus_flutter/features/knowledge/data/knowledge_api.dart';
import 'package:nexus_flutter/features/knowledge/domain/knowledge_document.dart';

final knowledgeApiProvider = Provider<KnowledgeApi>(
  (ref) => DioKnowledgeApi(ref.watch(dioProvider)),
);

final knowledgeControllerProvider =
    AsyncNotifierProvider<KnowledgeController, List<KnowledgeDocument>>(
      KnowledgeController.new,
    );

class KnowledgeController extends AsyncNotifier<List<KnowledgeDocument>> {
  @override
  Future<List<KnowledgeDocument>> build() => _load();

  Future<List<KnowledgeDocument>> _load() =>
      ref.read(knowledgeApiProvider).listDocuments();

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(_load);
  }

  Future<void> upload({
    required String filename,
    required List<int> bytes,
    required String mimeType,
  }) async {
    final api = ref.read(knowledgeApiProvider);
    final doc = await api.uploadDocument(
      filename: filename,
      bytes: bytes,
      mimeType: mimeType,
    );
    state = state.whenData((docs) => [doc, ...docs]);
  }

  Future<void> delete(String id) async {
    await ref.read(knowledgeApiProvider).deleteDocument(id);
    state = state.whenData((docs) => docs.where((d) => d.id != id).toList());
  }
}
