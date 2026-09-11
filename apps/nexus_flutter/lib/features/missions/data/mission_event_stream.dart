import 'dart:async';
import 'dart:convert';

import 'package:nexus_flutter/core/config/api_config.dart';
import 'package:nexus_flutter/features/missions/domain/mission_event.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

abstract interface class MissionSocket {
  Stream<Object?> get stream;

  Future<void> close();
}

abstract interface class MissionSocketConnector {
  Future<MissionSocket> connect(Uri uri);
}

class WebSocketMissionConnector implements MissionSocketConnector {
  const WebSocketMissionConnector();

  @override
  Future<MissionSocket> connect(Uri uri) async {
    final channel = WebSocketChannel.connect(uri);
    await channel.ready;
    return _WebSocketMissionSocket(channel);
  }
}

class ReconnectingMissionEventStream {
  const ReconnectingMissionEventStream({
    this.connector = const WebSocketMissionConnector(),
    this.maxReconnectAttempts = 5,
    this.baseDelay = const Duration(milliseconds: 300),
  });

  final MissionSocketConnector connector;
  final int maxReconnectAttempts;
  final Duration baseDelay;

  Stream<MissionEvent> watch(String runId, {int after = 0}) async* {
    var cursor = after;
    var attempts = 0;
    while (true) {
      MissionSocket? socket;
      try {
        socket = await connector.connect(_uri(runId, cursor));
        await for (final value in socket.stream) {
          final event = _decode(value);
          if (event.sequence <= cursor) {
            continue;
          }
          cursor = event.sequence;
          attempts = 0;
          yield event;
          if (event.isTerminal) {
            return;
          }
        }
      } catch (error) {
        attempts += 1;
        if (attempts > maxReconnectAttempts) {
          rethrow;
        }
      } finally {
        await socket?.close();
      }

      attempts += 1;
      if (attempts > maxReconnectAttempts) {
        throw StateError('The mission event stream could not reconnect.');
      }
      await Future<void>.delayed(baseDelay * attempts);
    }
  }

  static Uri _uri(String runId, int cursor) {
    final base = Uri.parse(ApiConfig.baseUrl);
    return base.replace(
      scheme: base.scheme == 'https' ? 'wss' : 'ws',
      path: '/ws/runs/${Uri.encodeComponent(runId)}',
      queryParameters: {'last_seen_sequence': '$cursor'},
    );
  }

  static MissionEvent _decode(Object? value) {
    final decoded = switch (value) {
      final String text => jsonDecode(text),
      final List<int> bytes => jsonDecode(utf8.decode(bytes)),
      _ => value,
    };
    if (decoded is! Map) {
      throw const FormatException('Invalid mission event payload.');
    }
    return MissionEvent.fromJson(Map<String, dynamic>.from(decoded));
  }
}

class _WebSocketMissionSocket implements MissionSocket {
  const _WebSocketMissionSocket(this.channel);

  final WebSocketChannel channel;

  @override
  Stream<Object?> get stream => channel.stream;

  @override
  Future<void> close() async {
    await channel.sink.close();
  }
}
