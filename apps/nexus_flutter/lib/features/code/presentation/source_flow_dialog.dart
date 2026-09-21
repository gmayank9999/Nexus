import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/code/application/code_providers.dart';

class SourceFlowDialog extends ConsumerStatefulWidget {
  const SourceFlowDialog({
    required this.request,
    required this.openSource,
    super.key,
  });
  final FlowRequest request;
  final void Function(String path, int line) openSource;

  @override
  ConsumerState<SourceFlowDialog> createState() => _FlowState();
}

class _FlowState extends ConsumerState<SourceFlowDialog> {
  final _root = TextEditingController();
  String _selectedRoot = '';

  @override
  void dispose() {
    _root.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final request = (entry: widget.request, root: _selectedRoot);
    return AlertDialog(
      title: Text('Source flow: ${widget.request.symbol}'),
      content: SizedBox(
        width: 800,
        height: 500,
        child: Column(
          children: [
            TextField(
              controller: _root,
              maxLength: 300,
              decoration: const InputDecoration(
                labelText: 'Flow source root',
                helperText:
                    'Optional ZIP directory, e.g. src. Blank uses ZIP root.',
              ),
            ),
            TextButton(
              onPressed: () {
                final root = _root.text.trim();
                ref.invalidate(
                  codeFlowProvider((entry: widget.request, root: root)),
                );
                setState(() => _selectedRoot = root);
              },
              child: const Text('Apply flow root'),
            ),
            Text(
              'Scope: ${_selectedRoot.isEmpty ? 'ZIP root' : _selectedRoot}',
            ),
            Expanded(
              child: ref
                  .watch(codeFlowProvider(request))
                  .when(
                    loading: () =>
                        const Center(child: CircularProgressIndicator()),
                    error: (_, _) => Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text(
                          'Could not inspect flow. Check the source root and select a uniquely named Python function; classes and duplicate names are not supported.',
                        ),
                        TextButton(
                          onPressed: () =>
                              ref.invalidate(codeFlowProvider(request)),
                          child: const Text('Retry flow'),
                        ),
                      ],
                    ),
                    data: (flow) {
                      final nodes = {
                        for (final node in flow.nodes) node.id: node,
                      };
                      return ListView(
                        children: [
                          const Text(
                            'Candidate graph — not a verified runtime trace',
                          ),
                          Text(flow.semantics),
                          if (flow.incomplete)
                            const Text(
                              'Index incomplete. Older snapshots need re-importing.',
                            ),
                          if (flow.truncated)
                            const Text(
                              'Graph limited: up to 25 nodes, 100 edges, depth 3.',
                            ),
                          for (final node in flow.nodes)
                            Card(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  ListTile(
                                    title: Text(node.name),
                                    subtitle: Text('${node.path}:${node.line}'),
                                    onTap: () =>
                                        widget.openSource(node.path, node.line),
                                  ),
                                  if (!flow.edges.any(
                                    (edge) => edge.source == node.id,
                                  ))
                                    const Padding(
                                      padding: EdgeInsets.all(12),
                                      child: Text(
                                        'No indexed calls for this node.',
                                      ),
                                    ),
                                  for (final edge in flow.edges.where(
                                    (edge) => edge.source == node.id,
                                  ))
                                    ListTile(
                                      leading: const Icon(
                                        Icons.subdirectory_arrow_right,
                                      ),
                                      title: Text(
                                        '${edge.callee} — line ${edge.line}',
                                      ),
                                      subtitle: Text(
                                        edge.target == null
                                            ? 'Unresolved: ${edge.resolution.replaceAll('_', ' ')}'
                                            : 'Candidate → ${nodes[edge.target]?.name ?? edge.target} (not verified)\n${nodes[edge.target]?.path}:${nodes[edge.target]?.line}',
                                      ),
                                      onTap: () => widget.openSource(
                                        node.path,
                                        edge.line,
                                      ),
                                      trailing: nodes[edge.target] == null
                                          ? null
                                          : IconButton(
                                              tooltip:
                                                  'Read candidate declaration',
                                              icon: const Icon(
                                                Icons.open_in_new,
                                              ),
                                              onPressed: () {
                                                final target =
                                                    nodes[edge.target]!;
                                                widget.openSource(
                                                  target.path,
                                                  target.line,
                                                );
                                              },
                                            ),
                                    ),
                                ],
                              ),
                            ),
                        ],
                      );
                    },
                  ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close flow'),
        ),
      ],
    );
  }
}
