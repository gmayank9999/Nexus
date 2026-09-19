/// Riverpod state for the memory feature.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/core/networking/api_client.dart';
import 'package:nexus_flutter/features/memory/data/memory_api.dart';
import 'package:nexus_flutter/features/memory/domain/nexus_memory.dart';

final memoryApiProvider = Provider<MemoryApi>(
  (ref) => DioMemoryApi(ref.watch(dioProvider)),
);

final memoryControllerProvider =
    AsyncNotifierProvider<MemoryController, List<NexusMemory>>(
      MemoryController.new,
    );

class MemoryController extends AsyncNotifier<List<NexusMemory>> {
  @override
  Future<List<NexusMemory>> build() => _load();

  Future<List<NexusMemory>> _load() =>
      ref.read(memoryApiProvider).listMemories();

  Future<void> refresh() async {
    ref.invalidateSelf();
  }

  Future<void> delete(String id) async {
    await ref.read(memoryApiProvider).deleteMemory(id);
    if (ref.mounted) ref.invalidateSelf();
  }

  Future<void> edit(String id, String content) async {
    await ref.read(memoryApiProvider).editMemory(id, content);
    if (ref.mounted) ref.invalidateSelf();
  }
}
