import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/code/application/code_providers.dart';
import 'package:nexus_flutter/features/code/presentation/call_sites_panel.dart';
import 'package:nexus_flutter/features/code/presentation/dependency_panel.dart';

class RepositoryScreen extends ConsumerStatefulWidget {
  const RepositoryScreen({required this.id, super.key});
  final String id;
  @override
  ConsumerState<RepositoryScreen> createState() => _RepositoryState();
}

class _RepositoryState extends ConsumerState<RepositoryScreen> {
  final _query = TextEditingController();
  String? _search;

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(RepositoryScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.id != widget.id) {
      _search = null;
      _query.clear();
    }
  }

  void _submit() {
    final query = _query.text.trim();
    if (query.isEmpty || query.runes.length > 100) return;
    final request = (id: widget.id, query: query);
    ref.invalidate(codeSearchProvider(request));
    setState(() => _search = query);
  }

  void _open(String path, int line) => showDialog<void>(
    context: context,
    builder: (_) => SourceDialog(id: widget.id, path: path, line: line),
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Repository source'),
      actions: [
        IconButton(
          tooltip: 'Refresh files',
          onPressed: () => ref.invalidate(repositoryFilesProvider(widget.id)),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(24),
      children: [
        DependencyPanel(
          key: ValueKey(widget.id),
          id: widget.id,
          openSource: _open,
        ),
        CallSitesPanel(
          key: ValueKey('calls:${widget.id}'),
          id: widget.id,
          openSource: _open,
        ),
        TextField(
          controller: _query,
          maxLength: 100,
          decoration: const InputDecoration(
            labelText: 'Search source',
            helperText: 'Literal text, up to 20 matches',
          ),
          onSubmitted: (_) => _submit(),
        ),
        Wrap(
          spacing: 8,
          children: [
            FilledButton(onPressed: _submit, child: const Text('Search')),
            if (_search != null)
              TextButton(
                onPressed: () => setState(() {
                  _search = null;
                  _query.clear();
                }),
                child: const Text('Clear search'),
              ),
          ],
        ),
        if (_search != null)
          ref
              .watch(codeSearchProvider((id: widget.id, query: _search!)))
              .when(
                loading: () => const LinearProgressIndicator(),
                error: (_, _) =>
                    const Text('Search failed. Press Search to retry.'),
                data: (result) => Column(
                  children: [
                    if (result.matches.isEmpty)
                      const Text('No matching lines.'),
                    for (final match in result.matches)
                      ListTile(
                        title: Text('${match.path}:${match.line}'),
                        subtitle: Text(
                          match.text,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        onTap: () => _open(match.path, match.line),
                      ),
                    if (result.truncated)
                      const Text(
                        'Only the first 20 matches are shown. Narrow your query.',
                      ),
                  ],
                ),
              ),
        const SizedBox(height: 24),
        const Text('Source files'),
        ref
            .watch(repositoryFilesProvider(widget.id))
            .when(
              loading: () => const LinearProgressIndicator(),
              error: (_, _) => const Text(
                'Could not load files. Use Refresh files to retry.',
              ),
              data: (index) => Column(
                children: [
                  Text(
                    '${index.skipped} unsupported or excluded files skipped',
                  ),
                  for (final file in index.files)
                    ExpansionTile(
                      key: ValueKey(file.path),
                      title: Text(file.path),
                      subtitle: Text(
                        '${file.language}${file.parseError ? ' · Python parse error' : ''}${file.truncated ? ' · Partial symbol index' : ''}',
                      ),
                      children: [
                        TextButton(
                          onPressed: () => _open(file.path, 1),
                          child: const Text('Read source'),
                        ),
                        for (final symbol in file.symbols)
                          ListTile(
                            title: Text(symbol.name),
                            subtitle: Text('Line ${symbol.line}'),
                            onTap: () => _open(file.path, symbol.line),
                          ),
                      ],
                    ),
                ],
              ),
            ),
      ],
    ),
  );
}

class SourceDialog extends ConsumerStatefulWidget {
  const SourceDialog({
    required this.id,
    required this.path,
    required this.line,
    super.key,
  });
  final String id;
  final String path;
  final int line;
  @override
  ConsumerState<SourceDialog> createState() => _SourceState();
}

class _SourceState extends ConsumerState<SourceDialog> {
  late int _line = widget.line;
  @override
  Widget build(BuildContext context) {
    final request = (id: widget.id, path: widget.path, line: _line);
    return AlertDialog(
      title: Text('${widget.path}:$_line'),
      content: SizedBox(
        width: 800,
        height: 450,
        child: ref
            .watch(codeSourceProvider(request))
            .when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (_, _) => TextButton(
                onPressed: () => ref.invalidate(codeSourceProvider(request)),
                child: const Text('Could not read source. Retry'),
              ),
              data: (source) => SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('SHA-256: ${source.hash}'),
                    if (source.truncated)
                      const Text(
                        'Bounded excerpt: up to 200 lines / 20,000 characters. Long lines may be cut.',
                      ),
                    SelectableText(
                      source.content
                          .split('\n')
                          .asMap()
                          .entries
                          .map(
                            (entry) =>
                                '${source.startLine + entry.key}  ${entry.value}',
                          )
                          .join('\n'),
                      style: const TextStyle(fontFamily: 'monospace'),
                    ),
                    if (_line + 200 <= source.totalLines)
                      TextButton(
                        onPressed: () => setState(() => _line += 200),
                        child: const Text('Next 200 lines'),
                      ),
                  ],
                ),
              ),
            ),
      ),
      actions: [
        if (_line > 1)
          TextButton(
            onPressed: () =>
                setState(() => _line = (_line - 200).clamp(1, _line)),
            child: const Text('Previous window'),
          ),
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    );
  }
}
