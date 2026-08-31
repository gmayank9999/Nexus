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
  const MissionStep({required this.title, required this.tool});

  factory MissionStep.fromJson(Map<String, dynamic> json) {
    return MissionStep(
      title: json['title'] as String? ?? 'Untitled step',
      tool: json['tool'] as String? ?? 'unknown',
    );
  }

  final String title;
  final String tool;
}

class MissionRun {
  const MissionRun({
    required this.id,
    required this.goal,
    required this.status,
    required this.steps,
    required this.traceCount,
    this.finalResponse,
    this.errorMessage,
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
  final String? finalResponse;
  final String? errorMessage;
}
