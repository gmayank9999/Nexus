import 'dart:typed_data';

import 'package:dio/dio.dart';

typedef Json = Map<String, dynamic>;

class RepositoryInfo {
  const RepositoryInfo(this.id, this.name, this.fileCount);
  factory RepositoryInfo.fromJson(Json json) => RepositoryInfo(
    json['id'] as String,
    json['name'] as String,
    json['file_count'] as int,
  );
  final String id;
  final String name;
  final int fileCount;
}

class IndexedFile {
  const IndexedFile(
    this.path,
    this.language,
    this.symbols,
    this.parseError,
    this.truncated,
  );
  factory IndexedFile.fromJson(Json json) => IndexedFile(
    json['path'] as String,
    json['language'] as String,
    (json['symbols'] as List<dynamic>).map((value) {
      final symbol = Map<String, dynamic>.from(value as Map);
      return (name: symbol['name'] as String, line: symbol['line'] as int);
    }).toList(),
    json['parse_error'] == true,
    json['index_truncated'] == true,
  );
  final String path;
  final String language;
  final List<({String name, int line})> symbols;
  final bool parseError;
  final bool truncated;
}

class CodeMatch {
  const CodeMatch(this.path, this.line, this.text);
  factory CodeMatch.fromJson(Json json) => CodeMatch(
    json['path'] as String,
    json['line'] as int,
    json['text'] as String,
  );
  final String path;
  final int line;
  final String text;
}

typedef FileIndex = ({List<IndexedFile> files, int skipped});

class ImportEdge {
  ImportEdge.fromJson(Json json)
    : source = json['source'] as String,
      target = json['target'] as String?,
      module = json['module'] as String,
      line = json['line'] as int,
      resolution = json['resolution'] as String,
      moduleTruncated = json['module_truncated'] == true;
  final String source;
  final String? target;
  final String module;
  final int line;
  final String resolution;
  final bool moduleTruncated;
}

typedef ImportGraph = ({
  List<ImportEdge> edges,
  bool truncated,
  bool incomplete,
});
typedef SearchResult = ({List<CodeMatch> matches, bool truncated});
typedef SourceWindow = ({
  String content,
  String hash,
  int startLine,
  int totalLines,
  bool truncated,
});

abstract interface class CodeApi {
  Future<List<RepositoryInfo>> list();
  Future<RepositoryInfo> upload(
    String name,
    Uint8List bytes,
    CancelToken cancel,
  );
  Future<FileIndex> files(String id);
  Future<ImportGraph> dependencies(String id, String root);
  Future<SearchResult> search(String id, String query);
  Future<SourceWindow> read(String id, String path, int line);
}

class DioCodeApi implements CodeApi {
  const DioCodeApi(this._dio);
  final Dio _dio;

  @override
  Future<ImportGraph> dependencies(String id, String root) async {
    final response = await _dio.get<Json>(
      '/api/v1/repositories/$id/dependencies',
      queryParameters: {'source_root': root},
    );
    final json = response.data!;
    return (
      edges: (json['edges'] as List<dynamic>)
          .map(
            (value) =>
                ImportEdge.fromJson(Map<String, dynamic>.from(value as Map)),
          )
          .toList(),
      truncated: json['truncated'] == true,
      incomplete: json['incomplete_index'] == true,
    );
  }

  @override
  Future<List<RepositoryInfo>> list() async {
    final response = await _dio.get<List<dynamic>>('/api/v1/repositories');
    return response.data!
        .map(
          (value) =>
              RepositoryInfo.fromJson(Map<String, dynamic>.from(value as Map)),
        )
        .toList();
  }

  @override
  Future<RepositoryInfo> upload(
    String name,
    Uint8List bytes,
    CancelToken cancel,
  ) async {
    final response = await _dio.post<Json>(
      '/api/v1/repositories',
      queryParameters: {'name': name},
      data: FormData.fromMap({
        'file': MultipartFile.fromBytes(bytes, filename: 'repository.zip'),
      }),
      cancelToken: cancel,
      options: Options(
        sendTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(seconds: 60),
      ),
    );
    return RepositoryInfo.fromJson(response.data!);
  }

  @override
  Future<FileIndex> files(String id) async {
    final response = await _dio.get<Json>('/api/v1/repositories/$id/files');
    final json = response.data!;
    return (
      files: (json['files'] as List<dynamic>)
          .map(
            (value) =>
                IndexedFile.fromJson(Map<String, dynamic>.from(value as Map)),
          )
          .toList(),
      skipped: json['skipped_files'] as int,
    );
  }

  @override
  Future<SearchResult> search(String id, String query) async {
    final response = await _dio.get<Json>(
      '/api/v1/repositories/$id/search',
      queryParameters: {'query': query},
    );
    final json = response.data!;
    return (
      matches: (json['matches'] as List<dynamic>)
          .map(
            (value) =>
                CodeMatch.fromJson(Map<String, dynamic>.from(value as Map)),
          )
          .toList(),
      truncated: json['truncated'] == true,
    );
  }

  @override
  Future<SourceWindow> read(String id, String path, int line) async {
    final response = await _dio.get<Json>(
      '/api/v1/repositories/$id/file',
      queryParameters: {'path': path, 'start_line': line},
    );
    final json = response.data!;
    return (
      content: json['content'] as String,
      hash: json['sha256'] as String,
      startLine: json['start_line'] as int,
      totalLines: json['total_lines'] as int,
      truncated: json['truncated'] == true,
    );
  }
}
