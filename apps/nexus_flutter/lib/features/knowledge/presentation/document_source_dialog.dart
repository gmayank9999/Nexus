import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/knowledge/application/knowledge_controller.dart';
import 'package:nexus_flutter/features/knowledge/domain/knowledge_document.dart';

typedef DocumentSourceRequest = ({String id, String? chunkId, int index});
final documentSourceProvider = FutureProvider.autoDispose
    .family<DocumentSource, DocumentSourceRequest>(
      (ref, request) => ref
          .watch(knowledgeApiProvider)
          .readSource(
            request.id,
            chunkId: request.chunkId,
            index: request.index,
          ),
    );

class DocumentSourceDialog extends ConsumerStatefulWidget {
  const DocumentSourceDialog({required this.id, this.chunkId, super.key});
  final String id;
  final String? chunkId;
  @override
  ConsumerState<DocumentSourceDialog> createState() => _SourceState();
}

class _SourceState extends ConsumerState<DocumentSourceDialog> {
  late String? _chunkId = widget.chunkId;
  int _index = 0;

  void _go(int index) => setState(() {
    _chunkId = null;
    _index = index;
  });

  @override
  Widget build(BuildContext context) {
    final request = (id: widget.id, chunkId: _chunkId, index: _index);
    return AlertDialog(
      title: const Text('Indexed document source'),
      content: SizedBox(
        width: 800,
        height: 450,
        child: ref
            .watch(documentSourceProvider(request))
            .when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (_, _) => Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Source unavailable. It may be deleted, not indexed, or outside this workspace.',
                  ),
                  TextButton(
                    onPressed: () =>
                        ref.invalidate(documentSourceProvider(request)),
                    child: const Text('Retry source'),
                  ),
                ],
              ),
              data: (source) => SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(source.title),
                    SelectableText(
                      'Document: ${source.documentId}\nChunk: ${source.chunkId}',
                    ),
                    Text('Chunk ${source.index + 1} of ${source.count}'),
                    Text(
                      source.page == null
                          ? 'Page not available in index'
                          : 'Page ${source.page}',
                    ),
                    if (source.section != null) Text(source.section!),
                    const Text(
                      'Extracted text, not the original file layout. Adjacent chunks can overlap.',
                    ),
                    if (source.truncated)
                      const Text('Excerpt capped at 20,000 characters.'),
                    const SizedBox(height: 12),
                    SelectableText(source.text),
                    Wrap(
                      children: [
                        if (source.index > 0)
                          TextButton(
                            onPressed: () => _go(source.index - 1),
                            child: const Text('Previous chunk'),
                          ),
                        if (source.index + 1 < source.count)
                          TextButton(
                            onPressed: () => _go(source.index + 1),
                            child: const Text('Next chunk'),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close source'),
        ),
      ],
    );
  }
}
