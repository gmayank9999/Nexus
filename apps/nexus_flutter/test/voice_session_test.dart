import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/voice/data/audio_stream_manager.dart';
import 'package:nexus_flutter/features/voice/data/realtime_session.dart';
import 'package:nexus_flutter/features/voice/domain/voice_state.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

void main() {
  test(
    'streams PCM, flushes the last audio before finish and returns review',
    () async {
      final fixture = await _Fixture.create();
      addTearDown(fixture.close);
      await fixture.session.start();
      fixture.mic.audio.add(Uint8List.fromList([1, 2]));
      await fixture.session.finish();
      await _until(
        () => fixture.states.any((s) => s.phase == VoicePhase.review),
      );
      expect(fixture.audio, [1, 2, 3, 4]);
      expect(fixture.states.last.text, 'Plan a study session');
      expect(fixture.states.last.isMock, isTrue);
      await fixture.session.close();
      expect(fixture.mic.disposed, isTrue);
    },
  );

  test('disabled server does not request the microphone', () async {
    final fixture = await _Fixture.create(disabled: true);
    addTearDown(fixture.close);
    await fixture.session.start();
    await _until(() => fixture.states.isNotEmpty);
    expect(fixture.states.last.phase, VoicePhase.error);
    expect(fixture.states.last.message, 'Voice is disabled on this server.');
    expect(fixture.mic.started, isFalse);
  });

  test(
    'permission denial closes the socket and exposes a useful message',
    () async {
      final fixture = await _Fixture.create();
      fixture.mic.denied = true;
      addTearDown(fixture.close);
      await fixture.session.start();
      await _until(() => fixture.states.isNotEmpty);
      expect(fixture.states.last.message, contains('permission'));
      await fixture.session.close();
      expect(fixture.mic.disposed, isTrue);
    },
  );

  test('close during microphone startup cannot start sending audio', () async {
    final fixture = await _Fixture.create();
    fixture.mic.startGate = Completer<void>();
    addTearDown(fixture.close);
    final starting = fixture.session.start();
    await _until(() => fixture.mic.started);
    await fixture.session.close();
    fixture.mic.startGate!.complete();
    await starting;
    expect(
      fixture.states.where((s) => s.phase == VoicePhase.recording),
      isEmpty,
    );
    expect(fixture.audio, isEmpty);
    expect(fixture.mic.disposed, isTrue);
  });

  test('odd PCM sample fails and releases microphone', () async {
    final fixture = await _Fixture.create();
    addTearDown(fixture.close);
    await fixture.session.start();
    fixture.mic.audio.add(Uint8List(1));
    await _until(() => fixture.states.any((s) => s.phase == VoicePhase.error));
    await fixture.session.close();
    expect(fixture.mic.disposed, isTrue);
  });

  test('audio byte limit auto-finishes and bounds outgoing frames', () async {
    final fixture = await _Fixture.create(seconds: 1);
    addTearDown(fixture.close);
    await fixture.session.start();
    fixture.mic.audio.add(Uint8List(64000));
    await _until(() => fixture.states.any((s) => s.phase == VoicePhase.review));
    expect(fixture.audio.length, 32000);
    expect(fixture.frameLengths.every((length) => length <= 16384), isTrue);
  });

  test('malformed server response releases microphone', () async {
    final fixture = await _Fixture.create();
    addTearDown(fixture.close);
    await fixture.session.start();
    fixture.socket!.add('not-json');
    await _until(() => fixture.states.any((s) => s.phase == VoicePhase.error));
    await fixture.session.close();
    expect(fixture.mic.disposed, isTrue);
  });
}

Future<void> _until(bool Function() done) async {
  final deadline = DateTime.now().add(const Duration(seconds: 3));
  while (!done()) {
    if (DateTime.now().isAfter(deadline)) {
      fail('Timed out waiting for voice state');
    }
    await Future<void>.delayed(const Duration(milliseconds: 2));
  }
}

class _Fixture {
  _Fixture(this.server);
  final HttpServer server;
  final mic = _Microphone();
  final states = <VoiceState>[];
  final audio = <int>[];
  final frameLengths = <int>[];
  late final RealtimeSession session;
  late final StreamSubscription<VoiceState> subscription;
  WebSocket? socket;

  static Future<_Fixture> create({
    bool disabled = false,
    int seconds = 60,
  }) async {
    final fixture = _Fixture(
      await HttpServer.bind(InternetAddress.loopbackIPv4, 0),
    );
    fixture.server.listen((request) async {
      final socket = await WebSocketTransformer.upgrade(request);
      fixture.socket = socket;
      socket.add(
        jsonEncode(
          disabled
              ? {
                  'type': 'error',
                  'message': 'Voice is disabled on this server.',
                }
              : {
                  'type': 'ready',
                  'format': 'pcm_s16le',
                  'sample_rate': 16000,
                  'channels': 1,
                  'max_seconds': seconds,
                },
        ),
      );
      socket.listen((message) {
        if (message is List<int>) {
          fixture.audio.addAll(message);
          fixture.frameLengths.add(message.length);
        } else if ((jsonDecode(message as String)
                as Map<String, dynamic>)['type'] ==
            'finish') {
          socket.add(
            jsonEncode({
              'type': 'transcript',
              'text': 'Plan a study session',
              'is_mock': true,
            }),
          );
        }
      });
    });
    fixture.session = RealtimeSession(
      microphoneFactory: () => fixture.mic,
      connect: (_) => WebSocketChannel.connect(
        Uri.parse('ws://127.0.0.1:${fixture.server.port}/ws/voice'),
      ),
    );
    fixture.subscription = fixture.session.updates.listen(fixture.states.add);
    return fixture;
  }

  Future<void> close() async {
    await session.close();
    await subscription.cancel();
    await socket?.close();
    await server.close(force: true);
  }
}

class _Microphone implements Microphone {
  final audio = StreamController<Uint8List>.broadcast();
  bool started = false;
  bool disposed = false;
  bool denied = false;
  Completer<void>? startGate;

  @override
  Future<Stream<Uint8List>> start() async {
    started = true;
    if (denied) throw StateError('Microphone permission denied.');
    await startGate?.future;
    return audio.stream;
  }

  @override
  Future<void> stop() async {
    if (!audio.isClosed) {
      audio.add(Uint8List.fromList([3, 4]));
      await audio.close();
    }
  }

  @override
  Future<void> dispose() async {
    disposed = true;
    if (!audio.isClosed) await audio.close();
  }
}
