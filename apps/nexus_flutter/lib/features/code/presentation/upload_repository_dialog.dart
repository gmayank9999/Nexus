import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/code/application/code_providers.dart';

class UploadRepositoryDialog extends ConsumerStatefulWidget {
  const UploadRepositoryDialog({super.key});
  @override
  ConsumerState<UploadRepositoryDialog> createState() => _UploadState();
}

class _UploadState extends ConsumerState<UploadRepositoryDialog> {
  final _name = TextEditingController();
  final _cancel = CancelToken();
  PickedArchive? _archive;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _cancel.cancel();
    _name.dispose();
    super.dispose();
  }

  Future<void> _pick() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final archive = await ref.read(archivePickerProvider)();
      if (!mounted) return;
      if (archive != null) {
        if (archive.bytes.length > maxArchiveBytes) {
          throw const FormatException();
        }
        setState(() {
          _archive = archive;
          _name.text = archive.name.replaceFirst(
            RegExp(r'\.zip$', caseSensitive: false),
            '',
          );
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Could not select the archive. Choose a ZIP of at most 5 MiB.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _upload() async {
    final archive = _archive;
    if (_busy || archive == null) return;
    final name = _name.text.trim();
    if (name.isEmpty || name.runes.length > 160) {
      setState(() => _error = 'Enter a name of 1 to 160 characters.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(codeApiProvider).upload(name, archive.bytes, _cancel);
      if (!mounted) return;
      ref.invalidate(repositoriesProvider);
      Navigator.of(context).pop();
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Import failed or its result is unknown. Refresh repositories before retrying to avoid duplicate snapshots.',
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
      title: const Text('Import repository ZIP'),
      content: SizedBox(
        width: 440,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Review the ZIP for secrets first. Source is uploaded and stored on your NEXUS server, never executed. Limit: 5 MiB; 200 source files. Each import creates a new snapshot.',
              ),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: _busy ? null : _pick,
                child: const Text('Choose ZIP'),
              ),
              if (_archive != null) ...[
                Text(_archive!.name),
                TextField(
                  controller: _name,
                  readOnly: _busy,
                  decoration: const InputDecoration(labelText: 'Snapshot name'),
                ),
              ],
              if (_error != null)
                Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _busy ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _busy || _archive == null ? null : _upload,
          child: Text(_busy ? 'Working...' : 'Upload snapshot'),
        ),
      ],
    ),
  );
}
