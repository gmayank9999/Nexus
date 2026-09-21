import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/knowledge/application/document_picker.dart';
import 'package:nexus_flutter/features/knowledge/application/knowledge_controller.dart';

class UploadDocumentDialog extends ConsumerStatefulWidget {
  const UploadDocumentDialog({super.key});
  @override
  ConsumerState<UploadDocumentDialog> createState() => _UploadState();
}

class _UploadState extends ConsumerState<UploadDocumentDialog> {
  PickedDocument? _selected;
  bool _busy = false;
  String? _error;

  Future<void> _choose() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final picked = await ref.read(documentPickerProvider)();
      if (!mounted || picked == null) return;
      if (picked.bytes.length > maxDocumentBytes) throw const FormatException();
      setState(() => _selected = picked);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Could not select document. Use PDF, TXT, MD or DOCX up to 20 MiB.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _upload() async {
    final selected = _selected;
    if (selected == null || _busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref
          .read(knowledgeControllerProvider.notifier)
          .upload(
            filename: selected.name,
            bytes: selected.bytes,
            mimeType: selected.mime,
          );
      if (mounted) Navigator.of(context).pop();
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Upload failed. The server may have accepted it. Close and refresh documents before retrying to avoid duplicates.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_busy,
    child: AlertDialog(
      title: const Text('Upload document'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'PDF, TXT, Markdown or DOCX, up to 20 MiB. Selection stays local until you confirm upload. Indexing happens on the server.',
            ),
            if (_selected != null) ...[
              const SizedBox(height: 12),
              Text(_selected!.name),
              Text('${_selected!.bytes.length} bytes'),
            ],
            if (_error != null) Text(_error!),
            if (_busy) const LinearProgressIndicator(),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _busy ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        TextButton(
          onPressed: _busy ? null : _choose,
          child: const Text('Choose document'),
        ),
        FilledButton(
          onPressed: _busy || _selected == null ? null : _upload,
          child: const Text('Upload selected document'),
        ),
      ],
    ),
  );
}
