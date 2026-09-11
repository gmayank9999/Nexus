/// Domain models for NEXUS memory.
library;

import 'package:flutter/foundation.dart';

enum MemoryCategory {
  userPreference,
  userGoal,
  userFact,
  projectContext,
  learningState,
  taskContext,
}

@immutable
class NexusMemory {
  const NexusMemory({
    required this.id,
    required this.category,
    required this.content,
    required this.confidence,
    required this.source,
    required this.createdAt,
    this.runId,
  });

  factory NexusMemory.fromJson(Map<String, dynamic> json) {
    return NexusMemory(
      id: json['id'] as String,
      category: _parseCategory(json['category'] as String),
      content: json['content'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      source: json['source'] as String,
      createdAt: json['created_at'] as String,
      runId: json['run_id'] as String?,
    );
  }

  final String id;
  final MemoryCategory category;
  final String content;
  final double confidence;
  final String source;
  final String createdAt;
  final String? runId;

  static MemoryCategory _parseCategory(String s) => switch (s) {
    'user_preference' => MemoryCategory.userPreference,
    'user_goal' => MemoryCategory.userGoal,
    'user_fact' => MemoryCategory.userFact,
    'project_context' => MemoryCategory.projectContext,
    'learning_state' => MemoryCategory.learningState,
    'task_context' => MemoryCategory.taskContext,
    _ => MemoryCategory.userFact,
  };

  String get categoryLabel => switch (category) {
    MemoryCategory.userPreference => 'Preference',
    MemoryCategory.userGoal => 'Goal',
    MemoryCategory.userFact => 'Fact',
    MemoryCategory.projectContext => 'Project',
    MemoryCategory.learningState => 'Learning',
    MemoryCategory.taskContext => 'Task',
  };
}
