import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/core/networking/api_client.dart';

final outputsApiProvider = Provider(
  (ref) => OutputsApi(ref.watch(dioProvider)),
);

class MissionTask {
  const MissionTask({
    required this.id,
    required this.runId,
    required this.title,
    required this.completed,
    this.description,
  });

  factory MissionTask.fromJson(Map<String, dynamic> json) => MissionTask(
    id: json['id'] as String,
    runId: json['run_id'] as String,
    title: json['title'] as String,
    completed: json['status'] == 'completed',
    description: json['description'] as String?,
  );

  final String id;
  final String runId;
  final String title;
  final String? description;
  final bool completed;
}

class MissionArtifact {
  const MissionArtifact({
    required this.id,
    required this.runId,
    required this.type,
    required this.title,
    required this.content,
  });

  factory MissionArtifact.fromJson(Map<String, dynamic> json) =>
      MissionArtifact(
        id: json['id'] as String,
        runId: json['run_id'] as String,
        type: json['type'] as String,
        title: json['title'] as String,
        content: json['content'] as String,
      );

  final String id;
  final String runId;
  final String type;
  final String title;
  final String content;

  String get typeLabel => type.replaceAll('_', ' ');
}

class OutputsApi {
  const OutputsApi(this._dio);
  final Dio _dio;

  Future<List<MissionTask>> tasks(String? runId) async {
    final result = await _dio.get<List<dynamic>>(
      '/api/v1/tasks',
      queryParameters: {'run_id': ?runId},
    );
    return (result.data ?? [])
        .map(
          (value) =>
              MissionTask.fromJson(Map<String, dynamic>.from(value as Map)),
        )
        .toList();
  }

  Future<void> setCompleted(String taskId, bool completed) async {
    await _dio.patch<void>(
      '/api/v1/tasks/$taskId',
      data: {'status': completed ? 'completed' : 'pending'},
    );
  }

  Future<List<MissionArtifact>> artifacts(String? runId) async {
    final result = await _dio.get<List<dynamic>>(
      '/api/v1/artifacts',
      queryParameters: {'run_id': ?runId},
    );
    return (result.data ?? [])
        .map(
          (value) =>
              MissionArtifact.fromJson(Map<String, dynamic>.from(value as Map)),
        )
        .toList();
  }
}

final tasksProvider = FutureProvider.autoDispose
    .family<List<MissionTask>, String?>(
      (ref, runId) => ref.watch(outputsApiProvider).tasks(runId),
    );
final artifactsProvider = FutureProvider.autoDispose
    .family<List<MissionArtifact>, String?>(
      (ref, runId) => ref.watch(outputsApiProvider).artifacts(runId),
    );
