import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:nexus_flutter/features/missions/data/mission_event_stream.dart';

void main() {
  test('reconnects with the last received sequence and avoids gaps', () async {
    final connector = _FakeConnector([
      [_event(1, 'run_created')],
      [_event(2, 'run_completed')],
    ]);
    final stream = ReconnectingMissionEventStream(
      connector: connector,
      baseDelay: Duration.zero,
    );

    final events = await stream.watch('run_1').toList();

    expect(events.map((event) => event.sequence), [1, 2]);
    expect(connector.uris, hasLength(2));
    expect(connector.uris[1].queryParameters['last_seen_sequence'], '1');
  });
}

String _event(int sequence, String type) => jsonEncode({
  'id': 'evt_$sequence',
  'run_id': 'run_1',
  'sequence': sequence,
  'type': type,
  'timestamp': '2026-09-01T00:00:00Z',
  'payload': <String, dynamic>{},
});

class _FakeConnector implements MissionSocketConnector {
  _FakeConnector(this.messages);

  final List<List<Object?>> messages;
  final List<Uri> uris = [];
  var _index = 0;

  @override
  Future<MissionSocket> connect(Uri uri) async {
    uris.add(uri);
    return _FakeSocket(Stream.fromIterable(messages[_index++]));
  }
}

class _FakeSocket implements MissionSocket {
  const _FakeSocket(this.stream);

  @override
  final Stream<Object?> stream;

  @override
  Future<void> close() async {}
}
