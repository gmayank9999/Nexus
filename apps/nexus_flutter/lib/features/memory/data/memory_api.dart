/// API client for memory read and delete operations.
library;

import 'package:dio/dio.dart';
import 'package:nexus_flutter/features/memory/domain/nexus_memory.dart';

abstract class MemoryApi {
  Future<List<NexusMemory>> listMemories();
  Future<void> deleteMemory(String id);
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
}
