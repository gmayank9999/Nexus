enum VoicePhase { idle, connecting, recording, transcribing, review, error }

class VoiceState {
  const VoiceState({
    this.phase = VoicePhase.idle,
    this.text = '',
    this.message,
    this.isMock = false,
    this.maxSeconds = 60,
  });

  final VoicePhase phase;
  final String text;
  final String? message;
  final bool isMock;
  final int maxSeconds;

  bool get isBusy => {
    VoicePhase.connecting,
    VoicePhase.recording,
    VoicePhase.transcribing,
  }.contains(phase);
}
