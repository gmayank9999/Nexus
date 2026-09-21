/// API client for document upload, list, and delete operations.
library;

import 'package:dio/dio.dart';
import 'package:nexus_flutter/features/knowledge/domain/knowledge_document.dart';

abstract class KnowledgeApi {
  Future<DocumentSource> readSource(
    String id, {
    String? chunkId,
    int index = 0,
  });
  Future<KnowledgeDocument> uploadDocument({
    required String filename,
    required List<int> bytes,
    required String mimeType,
  });

  Future<List<KnowledgeDocument>> listDocuments();

  Future<void> deleteDocument(String id);
}

class DioKnowledgeApi implements KnowledgeApi {
  const DioKnowledgeApi(this._dio);

  final Dio _dio;

  @override
  Future<DocumentSource> readSource(
    String id, {
    String? chunkId,
    int index = 0,
  }) async {
    final query = <String, dynamic>{'chunk_index': index};
    if (chunkId != null) query['chunk_id'] = chunkId;
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/documents/$id/source',
      queryParameters: query,
    );
    return DocumentSource.fromJson(response.data!);
  }

  @override
  Future<KnowledgeDocument> uploadDocument({
    required String filename,
    required List<int> bytes,
    required String mimeType,
  }) async {
    final formData = FormData.fromMap({
      'file': MultipartFile.fromBytes(
        bytes,
        filename: filename,
        contentType: DioMediaType.parse(mimeType),
      ),
    });
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/documents',
      data: formData,
      options: Options(
        sendTimeout: const Duration(seconds: 60),
        receiveTimeout: const Duration(seconds: 60),
      ),
    );
    return KnowledgeDocument.fromJson(response.data!);
  }

  @override
  Future<List<KnowledgeDocument>> listDocuments() async {
    final response = await _dio.get<List<dynamic>>('/api/v1/documents');
    return (response.data ?? [])
        .cast<Map<String, dynamic>>()
        .map(KnowledgeDocument.fromJson)
        .toList();
  }

  @override
  Future<void> deleteDocument(String id) async {
    await _dio.delete<void>('/api/v1/documents/$id');
  }
}
