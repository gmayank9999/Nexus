import 'package:nexus_flutter/features/missions/domain/mission_event.dart';

enum MissionRunStatus {
  created,
  planning,
  waitingForApproval,
  executing,
  observing,
  replanning,
  completed,
  failed,
  cancelled;

  factory MissionRunStatus.fromJson(String value) {
    return switch (value) {
      'created' => created,
      'planning' => planning,
      'waiting_for_approval' => waitingForApproval,
      'executing' => executing,
      'observing' => observing,
      'replanning' => replanning,
      'completed' => completed,
      'failed' => failed,
      'cancelled' => cancelled,
      _ => throw FormatException('Unknown mission status: $value'),
    };
  }
}

class MissionStep {
  const MissionStep({
    required this.title,
    required this.tool,
    this.description = '',
    this.requiresApproval = false,
  });

  factory MissionStep.fromJson(Map<String, dynamic> json) {
    return MissionStep(
      title: json['title'] as String? ?? 'Untitled step',
      tool: json['tool'] as String? ?? 'unknown',
      description: json['description'] as String? ?? '',
      requiresApproval: json['requires_approval'] as bool? ?? false,
    );
  }

  final String title;
  final String tool;
  final String description;
  final bool requiresApproval;
}

class MissionRun {
  const MissionRun({
    required this.id,
    required this.goal,
    required this.status,
    required this.steps,
    required this.traceCount,
    this.currentStep = 0,
    this.iteration = 0,
    this.maxIterations = 12,
    this.finalResponse,
    this.errorMessage,
    this.events = const [],
  });

  factory MissionRun.fromJson(Map<String, dynamic> json) {
    final plan = json['plan'];
    final stepsValue = plan is Map<String, dynamic> ? plan['steps'] : null;
    final steps = stepsValue is List<dynamic>
        ? stepsValue
              .whereType<Map<String, dynamic>>()
              .map(MissionStep.fromJson)
              .toList(growable: false)
        : const <MissionStep>[];
    final trace = json['trace'];
    final error = json['error'];
    return MissionRun(
      id: json['id'] as String,
      goal: json['goal'] as String,
      status: MissionRunStatus.fromJson(json['status'] as String),
      steps: steps,
      traceCount: trace is List<dynamic> ? trace.length : 0,
      events: trace is List<dynamic>
          ? trace
                .whereType<Map<String, dynamic>>()
                .where((event) => event.containsKey('sequence'))
                .map(MissionEvent.fromJson)
                .toList(growable: false)
          : const [],
      currentStep: json['current_step'] as int? ?? 0,
      iteration: json['iteration'] as int? ?? 0,
      maxIterations: json['max_iterations'] as int? ?? 12,
      finalResponse: json['final_response'] as String?,
      errorMessage: error is Map<String, dynamic>
          ? error['message'] as String?
          : null,
    );
  }

  final String id;
  final String goal;
  final MissionRunStatus status;
  final List<MissionStep> steps;
  final int traceCount;
  final int currentStep;
  final int iteration;
  final int maxIterations;
  final String? finalResponse;
  final String? errorMessage;
  final List<MissionEvent> events;

  bool get isTerminal => const {
    MissionRunStatus.completed,
    MissionRunStatus.failed,
    MissionRunStatus.cancelled,
  }.contains(status);

  double get progress => status == MissionRunStatus.completed
      ? 1
      : steps.isEmpty
      ? 0
      : (currentStep / steps.length).clamp(0.0, 1.0);

  String get statusLabel => switch (status) {
    MissionRunStatus.waitingForApproval => 'Needs approval',
    _ => '${status.name[0].toUpperCase()}${status.name.substring(1)}',
  };

  MissionRun copyWith({
    MissionRunStatus? status,
    List<MissionStep>? steps,
    int? traceCount,
    int? currentStep,
    int? iteration,
    String? finalResponse,
    String? errorMessage,
  }) {
    return MissionRun(
      id: id,
      goal: goal,
      status: status ?? this.status,
      steps: steps ?? this.steps,
      traceCount: traceCount ?? this.traceCount,
      currentStep: currentStep ?? this.currentStep,
      iteration: iteration ?? this.iteration,
      maxIterations: maxIterations,
      finalResponse: finalResponse ?? this.finalResponse,
      errorMessage: errorMessage ?? this.errorMessage,
      events: events,
    );
  }

  MissionRun applyEvent(MissionEvent event) {
    var nextStatus = status;
    var nextSteps = steps;
    var nextCurrentStep = currentStep;
    var nextFinalResponse = finalResponse;
    var nextErrorMessage = errorMessage;

    if (event.type == 'status_changed') {
      final value = event.payload['to'];
      if (value is String) {
        nextStatus = MissionRunStatus.fromJson(value);
      }
    } else if (event.type == 'plan_created') {
      final plan = event.payload['plan'];
      final values = plan is Map ? plan['steps'] : null;
      if (values is List<dynamic>) {
        nextSteps = values
            .whereType<Map>()
            .map(
              (value) => MissionStep.fromJson(Map<String, dynamic>.from(value)),
            )
            .toList(growable: false);
      }
      nextCurrentStep = 0;
    } else if (event.type == 'tool_completed') {
      nextCurrentStep += 1;
    } else if (event.type == 'run_completed') {
      nextStatus = MissionRunStatus.completed;
      nextFinalResponse = event.payload['response'] as String?;
    } else if (event.type == 'run_failed') {
      nextStatus = MissionRunStatus.failed;
      nextErrorMessage = event.payload['message'] as String?;
    } else if (event.type == 'run_cancelled') {
      nextStatus = MissionRunStatus.cancelled;
    }

    return copyWith(
      status: nextStatus,
      steps: nextSteps,
      traceCount: event.sequence,
      currentStep: nextCurrentStep,
      finalResponse: nextFinalResponse,
      errorMessage: nextErrorMessage,
    );
  }
}
