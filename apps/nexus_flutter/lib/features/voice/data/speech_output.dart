/// Speech implementations consume only the final response from NEXUS.
/// Future adapters can use a self-hosted synthesizer without changing the UI.
abstract interface class SpeechOutput {
  /// Completes when playback ends or is stopped. Errors must not expose text.
  Future<void> speak(String text);
  Future<void> stop();
  Future<void> dispose();
}

class SpeechOutputUnavailable implements Exception {
  const SpeechOutputUnavailable(this.message);
  final String message;
}
