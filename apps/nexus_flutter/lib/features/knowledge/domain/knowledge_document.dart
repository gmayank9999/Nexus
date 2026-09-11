/// Domain models for documents in the knowledge base.
library;

import 'package:flutter/foundation.dart';

enum DocumentStatus { pending, indexing, indexed, failed }

@immutable
class KnowledgeDocument {
  const KnowledgeDocument({
    required this.id,
    required this.title,
    required this.status,
    required this.mimeType,
    required this.sizeBytes,
    required this.chunkCount,
    this.error,
  });

  factory KnowledgeDocument.fromJson(Map<String, dynamic> json) {
    return KnowledgeDocument(
      id: json['id'] as String,
      title: json['title'] as String,
      status: _parseStatus(json['status'] as String),
      mimeType: json['mime_type'] as String,
      sizeBytes: json['size_bytes'] as int,
      chunkCount: json['chunk_count'] as int,
      error: json['error'] as String?,
    );
  }

  final String id;
  final String title;
  final DocumentStatus status;
  final String mimeType;
  final int sizeBytes;
  final int chunkCount;
  final String? error;

  static DocumentStatus _parseStatus(String s) => switch (s) {
    'pending' => DocumentStatus.pending,
    'indexing' => DocumentStatus.indexing,
    'indexed' => DocumentStatus.indexed,
    'failed' => DocumentStatus.failed,
    _ => DocumentStatus.pending,
  };

  String get humanSize {
    if (sizeBytes < 1024) return '$sizeBytes B';
    if (sizeBytes < 1024 * 1024)
      return '${(sizeBytes / 1024).toStringAsFixed(1)} KB';
    return '${(sizeBytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
}
