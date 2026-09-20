/// Knowledge base screen: document list, upload, and deletion.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:nexus_flutter/features/knowledge/application/knowledge_controller.dart';
import 'package:nexus_flutter/features/knowledge/domain/knowledge_document.dart';

class KnowledgeScreen extends ConsumerWidget {
  const KnowledgeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(knowledgeControllerProvider);
    return CustomScrollView(
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(24, 28, 24, 96),
          sliver: SliverList.list(
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Knowledge',
                          style: Theme.of(context).textTheme.headlineLarge,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Upload documents for the agent to read and cite',
                          style: Theme.of(context).textTheme.bodyLarge
                              ?.copyWith(
                                color: Theme.of(
                                  context,
                                ).colorScheme.onSurfaceVariant,
                              ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  _UploadButton(),
                ],
              ),
              const SizedBox(height: 24),
              OutlinedButton.icon(
                onPressed: () => context.push('/repositories'),
                icon: const Icon(Icons.code),
                label: const Text('Browse code repositories'),
              ),
              state.when(
                loading: () => const _LoadingPlaceholder(),
                error: (err, _) => _ErrorCard(message: err.toString()),
                data: (docs) => docs.isEmpty
                    ? const _EmptyState()
                    : _DocumentList(docs: docs),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------

class _UploadButton extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return FilledButton.icon(
      onPressed: () => _showUploadDialog(context, ref),
      icon: const Icon(Icons.upload_file),
      label: const Text('Upload'),
    );
  }

  void _showUploadDialog(BuildContext context, WidgetRef ref) {
    showDialog<void>(
      context: context,
      builder: (_) => _UploadDialog(ref: ref),
    );
  }
}

class _UploadDialog extends StatefulWidget {
  const _UploadDialog({required this.ref});

  final WidgetRef ref;

  @override
  State<_UploadDialog> createState() => _UploadDialogState();
}

class _UploadDialogState extends State<_UploadDialog> {
  // ignore: prefer_final_fields - mutated in setState
  bool _uploading = false;
  String? _error;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Upload Document'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Supported formats: PDF, TXT, Markdown, DOCX (max 20 MB).',
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: _uploading ? null : () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton.icon(
          onPressed: _uploading ? null : () => _pickAndUpload(context),
          icon: _uploading
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.upload),
          label: const Text('Choose File'),
        ),
      ],
    );
  }

  Future<void> _pickAndUpload(BuildContext context) async {
    // On web/desktop, flutter doesn't have a built-in file picker in the std library.
    // We use a simple text-field approach for the demo and show a snackbar.
    // In a real production build you'd integrate file_picker package.
    setState(() {
      _error =
          'File picker not bundled in this build. '
          'Drop a file via the API at POST /api/v1/documents.';
    });
  }
}

// ---------------------------------------------------------------------------

class _DocumentList extends ConsumerWidget {
  const _DocumentList({required this.docs});

  final List<KnowledgeDocument> docs;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Column(children: [for (final doc in docs) _DocumentTile(doc: doc)]);
  }
}

class _DocumentTile extends ConsumerWidget {
  const _DocumentTile({required this.doc});

  final KnowledgeDocument doc;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final color = _statusColor(doc.status);
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
        leading: _MimeIcon(mime: doc.mimeType),
        title: Text(doc.title, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 3,
                  ),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(99),
                  ),
                  child: Text(
                    doc.status.name,
                    style: Theme.of(
                      context,
                    ).textTheme.labelSmall?.copyWith(color: color),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  doc.humanSize,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                if (doc.chunkCount > 0) ...[
                  const SizedBox(width: 8),
                  Text(
                    '${doc.chunkCount} chunks',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ],
            ),
            if (doc.error != null) ...[
              const SizedBox(height: 4),
              Text(
                doc.error!,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.error,
                  fontSize: 12,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ],
        ),
        trailing: IconButton(
          icon: const Icon(Icons.delete_outline),
          tooltip: 'Delete',
          onPressed: () => _confirmDelete(context, ref),
        ),
        isThreeLine: doc.error != null,
      ),
    );
  }

  Future<void> _confirmDelete(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete document?'),
        content: Text(
          'This will permanently remove "${doc.title}" and all its indexed chunks.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await ref.read(knowledgeControllerProvider.notifier).delete(doc.id);
    }
  }
}

// ---------------------------------------------------------------------------

class _MimeIcon extends StatelessWidget {
  const _MimeIcon({required this.mime});

  final String mime;

  @override
  Widget build(BuildContext context) {
    final IconData icon = switch (mime) {
      'application/pdf' => Icons.picture_as_pdf,
      'text/plain' || 'text/markdown' => Icons.description,
      final String m when m.contains('word') => Icons.article,
      _ => Icons.insert_drive_file,
    };
    return Icon(icon, size: 32, color: const Color(0xFF42D6FF));
  }
}

Color _statusColor(DocumentStatus status) => switch (status) {
  DocumentStatus.indexed => const Color(0xFF54E6A5),
  DocumentStatus.failed => const Color(0xFFFF6B7A),
  DocumentStatus.indexing => const Color(0xFFFFC857),
  DocumentStatus.pending => const Color(0xFF42D6FF),
};

class _LoadingPlaceholder extends StatelessWidget {
  const _LoadingPlaceholder();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(48),
        child: CircularProgressIndicator(),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(32),
        child: Column(
          children: [
            Icon(Icons.library_books_rounded, size: 48),
            SizedBox(height: 12),
            Text(
              'No documents yet.',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            SizedBox(height: 6),
            Text(
              'Upload PDF, TXT, Markdown, or DOCX files for NEXUS to read and cite during missions.',
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Theme.of(context).colorScheme.errorContainer,
      child: Padding(padding: const EdgeInsets.all(16), child: Text(message)),
    );
  }
}
