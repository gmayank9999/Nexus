/// API client for workspace-scoped memory controls.
library;

import 'package:dio/dio.dart';
import 'package:nexus_flutter/features/memory/domain/nexus_memory.dart';

abstract class MemoryApi {
  Future<List<NexusMemory>> listMemories();
  Future<void> deleteMemory(String id);
  Future<NexusMemory> editMemory(String id, String content);
}

class DioMemoryApi implements MemoryApi {
  const DioMemoryApi(this._dio);

  final Dio _dio;

  @override
  Future<List<NexusMemory>> listMemories() async {
    final response = await _dio.get<List<dynamic>>('/api/v1/memories');
    return (response.data ?? [])
        .cast<Map<String, dynamic>>()
        .map(NexusMemory.fromJson)
        .toList();
  }

  @override
  Future<void> deleteMemory(String id) async {
    await _dio.delete<void>('/api/v1/memories/$id');
  }

  @override
  Future<NexusMemory> editMemory(String id, String content) async {
    final response = await _dio.patch<Map<String, dynamic>>(
      '/api/v1/memories/$id',
      data: {'content': content},
    );
    if (response.data == null) {
      throw const FormatException('The backend returned an empty memory.');
    }
    return NexusMemory.fromJson(response.data!);
  }
}
