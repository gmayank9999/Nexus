class MissionEvent {
  const MissionEvent({
    required this.id,
    required this.runId,
    required this.sequence,
    required this.type,
    required this.timestamp,
    required this.payload,
  });

  factory MissionEvent.fromJson(Map<String, dynamic> json) {
    final rawPayload = json['payload'];
    return MissionEvent(
      id: json['id'] as String,
      runId: json['run_id'] as String,
      sequence: json['sequence'] as int,
      type: json['type'] as String,
      timestamp: DateTime.parse(json['timestamp'] as String),
      payload: rawPayload is Map<String, dynamic>
          ? rawPayload
          : <String, dynamic>{},
    );
  }

  final String id;
  final String runId;
  final int sequence;
  final String type;
  final DateTime timestamp;
  final Map<String, dynamic> payload;

  bool get isTerminal =>
      const {'run_completed', 'run_failed', 'run_cancelled'}.contains(type);
}
