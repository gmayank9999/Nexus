import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/code/application/code_providers.dart';

class DependencyPanel extends ConsumerStatefulWidget {
  const DependencyPanel({
    required this.id,
    required this.openSource,
    super.key,
  });
  final String id;
  final void Function(String path, int line) openSource;

  @override
  ConsumerState<DependencyPanel> createState() => _DependencyState();
}

class _DependencyState extends ConsumerState<DependencyPanel> {
  final _root = TextEditingController();
  String? _selectedRoot;

  @override
  void dispose() {
    _root.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final request = (id: widget.id, root: _selectedRoot ?? '');
    return ExpansionTile(
      title: const Text('Python import dependencies'),
      childrenPadding: const EdgeInsets.all(12),
      children: [
        const Text(
          'Declared imports only — not a runtime or call graph. '
          'Unresolved imports are not necessarily external.',
        ),
        TextField(
          controller: _root,
          maxLength: 300,
          decoration: const InputDecoration(
            labelText: 'Snapshot source root',
            helperText:
                'Optional, e.g. src or project/src. Blank uses the ZIP root.',
          ),
        ),
        TextButton(
          onPressed: () {
            final root = _root.text.trim();
            ref.invalidate(
              codeDependenciesProvider((id: widget.id, root: root)),
            );
            setState(() => _selectedRoot = root);
          },
          child: const Text('Load dependencies'),
        ),
        if (_selectedRoot != null)
          ref
              .watch(codeDependenciesProvider(request))
              .when(
                loading: () => const LinearProgressIndicator(),
                error: (_, _) => const Text(
                  'Could not load dependencies. Check the source root and press Load dependencies to retry.',
                ),
                data: (graph) => Column(
                  children: [
                    Text(
                      'Scope: ${request.root.isEmpty ? 'ZIP root' : request.root}',
                    ),
                    if (graph.incomplete)
                      const Text('Source index is incomplete.'),
                    if (graph.truncated)
                      const Text('Only the first 500 imports are shown.'),
                    if (graph.edges.isEmpty)
                      const Text('No indexed imports in this scope.'),
                    for (final edge in graph.edges)
                      ListTile(
                        title: Text(
                          '${edge.source}:${edge.line} imports ${edge.module}${edge.moduleTruncated ? '… (label truncated)' : ''}',
                        ),
                        subtitle: Text(
                          edge.target ?? edge.resolution.replaceAll('_', ' '),
                        ),
                        onTap: () => widget.openSource(edge.source, edge.line),
                        trailing: edge.target == null
                            ? null
                            : IconButton(
                                tooltip: 'Read imported module',
                                icon: const Icon(Icons.open_in_new),
                                onPressed: () =>
                                    widget.openSource(edge.target!, 1),
                              ),
                      ),
                  ],
                ),
              ),
      ],
    );
  }
}
