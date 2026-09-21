import 'package:flutter/material.dart';
import 'package:nexus_flutter/features/knowledge/presentation/document_source_dialog.dart';
import 'package:nexus_flutter/features/missions/domain/mission_event.dart';

class DocumentCitations extends StatelessWidget {
  const DocumentCitations({required this.events, super.key});
  final List<MissionEvent> events;

  @override
  Widget build(BuildContext context) {
    final sources = <({String id, String chunk}), String>{};
    final validId = RegExp(r'^[a-zA-Z0-9_-]{1,80}$');
    for (final event in events) {
      if (event.type != 'tool_completed' ||
          event.payload['tool'] != 'search_files') {
        continue;
      }
      final output = event.payload['output'];
      final matches = output is Map ? output['matches'] : null;
      if (matches is! List) continue;
      for (final match in matches) {
        if (match is! Map || sources.length >= 50) continue;
        final id = match['document_id'];
        final chunk = match['chunk_id'];
        if (id is! String ||
            chunk is! String ||
            !validId.hasMatch(id) ||
            !validId.hasMatch(chunk)) {
          continue;
        }
        final title = match['title'] is String
            ? match['title'] as String
            : 'Document';
        sources[(id: id, chunk: chunk)] = title.length > 200
            ? title.substring(0, 200)
            : title;
      }
    }
    if (sources.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Retrieved sources (up to 50; not proof of the answer)'),
        for (final source in sources.entries)
          TextButton.icon(
            icon: const Icon(Icons.description_outlined),
            label: Text(source.value),
            onPressed: () => showDialog<void>(
              context: context,
              builder: (_) => DocumentSourceDialog(
                id: source.key.id,
                chunkId: source.key.chunk,
              ),
            ),
          ),
      ],
    );
  }
}
