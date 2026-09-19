import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:nexus_flutter/core/config/api_config.dart';
import 'package:nexus_flutter/features/voice/data/audio_stream_manager.dart';
import 'package:nexus_flutter/features/voice/domain/voice_state.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

abstract interface class VoiceSession {
  Stream<VoiceState> get updates;
  Future<void> start();
  Future<void> finish();
  Future<void> close();
}

/// One bounded utterance. Never reconnects or silently resends microphone audio.
class RealtimeSession implements VoiceSession {
  RealtimeSession({
    Microphone Function()? microphoneFactory,
    WebSocketChannel Function(Uri)? connect,
  }) : _microphoneFactory = microphoneFactory ?? AudioStreamManager.new,
       _connect = connect ?? WebSocketChannel.connect;

  final Microphone Function() _microphoneFactory;
  final WebSocketChannel Function(Uri) _connect;
  final _updates = StreamController<VoiceState>();
  final _ready = Completer<int>();
  final _audioDone = Completer<void>();
  WebSocketChannel? _channel;
  Microphone? _microphone;
  StreamSubscription<Object?>? _socketSubscription;
  StreamSubscription<Uint8List>? _audioSubscription;
  Timer? _timer;
  bool _closed = false;
  bool _finishing = false;
  bool _terminal = false;
  int _bytesSent = 0;
  int _maxSeconds = 60;
  Future<void>? _cleanup;

  @override
  Stream<VoiceState> get updates => _updates.stream;

  @override
  Future<void> start() async {
    // A server error can arrive before channel.ready resolves.
    _ready.future.ignore();
    try {
      final base = Uri.parse(ApiConfig.baseUrl);
      final channel = _connect(
        base.replace(
          scheme: base.scheme == 'https' ? 'wss' : 'ws',
          path: '/ws/voice',
          query: '',
          fragment: '',
        ),
      );
      _channel = channel;
      _socketSubscription = channel.stream.listen(
        _onMessage,
        onError: (Object error) =>
            _fail('Cannot connect to the voice service.'),
        onDone: () {
          if (!_terminal && !_closed) {
            _fail('Voice connection closed. Try again.');
          }
        },
      );
      await channel.ready.timeout(const Duration(seconds: 10));
      _maxSeconds = await _ready.future.timeout(const Duration(seconds: 10));
      if (_closed) return;
      final microphone = _microphoneFactory();
      _microphone = microphone;
      final audio = await microphone.start();
      if (_closed) {
        await microphone.stop();
        return;
      }
      _audioSubscription = audio.listen(
        _sendAudio,
        onError: (Object error) =>
            _fail('Microphone recording failed. Try again.'),
        onDone: () {
          if (!_audioDone.isCompleted) _audioDone.complete();
          if (!_finishing && !_closed) unawaited(finish());
        },
      );
      _emit(VoiceState(phase: VoicePhase.recording, maxSeconds: _maxSeconds));
      _timer = Timer(Duration(seconds: _maxSeconds), () => unawaited(finish()));
    } catch (error) {
      _fail(
        error is StateError
            ? error.message
            : 'Could not start voice input. Check microphone permissions and server settings.',
      );
    }
  }

  void _sendAudio(Uint8List bytes) {
    if (_closed) return;
    // Bound the entire socket queue even if the network stops draining.
    final available = _maxSeconds * 32000 - _bytesSent;
    final length = min(available, bytes.length);
    if (length.isOdd) {
      _fail('The microphone returned an unsupported audio format.');
      return;
    }
    try {
      for (var offset = 0; offset < length; offset += 16384) {
        _channel!.sink.add(
          Uint8List.sublistView(bytes, offset, min(offset + 16384, length)),
        );
      }
    } catch (_) {
      _fail('Audio connection failed. Please try again.');
      return;
    }
    _bytesSent += length;
    if (length < bytes.length || _bytesSent >= _maxSeconds * 32000) {
      unawaited(finish());
    }
  }

  void _onMessage(Object? raw) {
    if (_closed) return;
    try {
      final event = jsonDecode(raw as String) as Map<String, dynamic>;
      switch (event['type']) {
        case 'ready':
          if (_ready.isCompleted ||
              event['format'] != 'pcm_s16le' ||
              event['sample_rate'] != 16000 ||
              event['channels'] != 1) {
            throw const FormatException();
          }
          final seconds = event['max_seconds'] as int;
          if (seconds < 1 || seconds > 120) throw const FormatException();
          _ready.complete(seconds);
        case 'transcribing':
          _emit(const VoiceState(phase: VoicePhase.transcribing));
        case 'transcript':
          if (!_finishing) throw const FormatException();
          final text = (event['text'] as String).trim();
          if (text.isEmpty || text.length > 4000) throw const FormatException();
          _terminal = true;
          _emit(
            VoiceState(
              phase: VoicePhase.review,
              text: text,
              isMock: event['is_mock'] == true,
            ),
          );
          unawaited(close());
        case 'error':
          _fail(event['message'] as String? ?? 'Voice input failed.');
        case 'cancelled':
          unawaited(close());
        default:
          throw const FormatException();
      }
    } catch (_) {
      _fail('The voice service returned an invalid response.');
    }
  }

  @override
  Future<void> finish() async {
    if (_closed || _finishing || _microphone == null) return;
    _finishing = true;
    _timer?.cancel();
    _emit(const VoiceState(phase: VoicePhase.transcribing));
    try {
      await _microphone!.stop();
      // record documents that stream closure, not stop(), delivers the last bytes.
      await _audioDone.future.timeout(const Duration(seconds: 5));
      if (_closed) return;
      _channel!.sink.add(jsonEncode({'type': 'finish'}));
      _timer = Timer(
        const Duration(seconds: 190),
        () => _fail('Transcription timed out. Try again.'),
      );
    } catch (_) {
      _fail('Could not finish recording. Please try again.');
    }
  }

  void _emit(VoiceState value) {
    if (!_closed) _updates.add(value);
  }

  void _fail(String message) {
    if (_closed) return;
    _terminal = true;
    if (!_ready.isCompleted) _ready.completeError(StateError(message));
    _emit(VoiceState(phase: VoicePhase.error, message: message));
    unawaited(close());
  }

  @override
  Future<void> close() => _cleanup ??= _close();

  Future<void> _close() async {
    _closed = true;
    _timer?.cancel();
    _ready.future.ignore();
    if (!_ready.isCompleted) {
      _ready.completeError(StateError('Voice input cancelled.'));
    }
    // Release the microphone immediately, even if socket closure is slow.
    final disposal = _disposeMicrophone();
    // Disconnect also cancels an in-flight backend transcription.
    try {
      await _channel?.sink.close().timeout(const Duration(seconds: 2));
    } catch (_) {
      /* Already disconnected. */
    }
    await _socketSubscription?.cancel();
    await _audioSubscription?.cancel();
    await disposal;
    unawaited(_updates.close());
  }

  Future<void> _disposeMicrophone() async {
    try {
      await _microphone?.dispose();
    } catch (_) {
      /* Device already removed. */
    }
  }
}
