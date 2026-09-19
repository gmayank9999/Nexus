import 'dart:typed_data';

import 'package:record/record.dart';

abstract interface class Microphone {
  Future<Stream<Uint8List>> start();
  Future<void> stop();
  Future<void> dispose();
}

class AudioStreamManager implements Microphone {
  final _recorder = AudioRecorder();
  bool _disposed = false;
  bool _unsupportedFormat = false;

  @override
  Future<Stream<Uint8List>> start() async {
    if (!await _recorder.hasPermission()) {
      throw StateError(
        'Microphone permission was denied. Enable it and try again.',
      );
    }
    if (_disposed) throw StateError('Voice input cancelled.');
    await _recorder.setOnConfigChanged((config) {
      _unsupportedFormat =
          config.sampleRate != 16000 ||
          config.numChannels != 1 ||
          config.encoder != AudioEncoder.pcm16bits;
    });
    if (_disposed) throw StateError('Voice input cancelled.');
    final audio = await _recorder.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
      ),
    );
    return audio.map((chunk) {
      if (_unsupportedFormat) {
        throw StateError('This microphone does not support 16 kHz mono PCM16.');
      }
      return chunk;
    });
  }

  @override
  Future<void> stop() async {
    await _recorder.stop();
  }

  @override
  Future<void> dispose() {
    _disposed = true;
    return _recorder.dispose();
  }
}
