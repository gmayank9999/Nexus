import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/code/application/code_providers.dart';

class CallSitesPanel extends ConsumerStatefulWidget {
  const CallSitesPanel({required this.id, required this.openSource, super.key});
  final String id;
  final void Function(String path, int line) openSource;

  @override
  ConsumerState<CallSitesPanel> createState() => _CallSitesState();
}

class _CallSitesState extends ConsumerState<CallSitesPanel> {
  bool _loaded = false;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    title: const Text('Python call sites'),
    childrenPadding: const EdgeInsets.all(12),
    children: [
      const Text(
        'Syntactic calls in lexical scopes, not resolved targets or execution order. '
        'Defaults and decorators can execute outside their lexical scope.',
      ),
      TextButton(
        onPressed: () {
          ref.invalidate(codeCallsProvider(widget.id));
          setState(() => _loaded = true);
        },
        child: const Text('Load call sites'),
      ),
      if (_loaded)
        ref
            .watch(codeCallsProvider(widget.id))
            .when(
              loading: () => const LinearProgressIndicator(),
              error: (_, _) => const Text(
                'Could not load call sites. Press Load call sites to retry.',
              ),
              data: (index) => Column(
                children: [
                  if (index.incomplete)
                    const Text(
                      'Call index is incomplete. Older snapshots need re-importing; unsupported or invalid files may also be missing.',
                    ),
                  if (index.truncated)
                    const Text(
                      'Call results are capped at 500; some evidence is omitted.',
                    ),
                  if (index.calls.isEmpty)
                    const Text(
                      'No indexed call sites. This does not prove there are no calls.',
                    ),
                  for (final call in index.calls)
                    ListTile(
                      title: Text(
                        '${call.path}:${call.line} calls ${call.callee}',
                      ),
                      subtitle: Text(
                        'Lexical scope: ${call.scope}'
                        '${call.dynamicExpression ? '\nDynamic expression: unresolved' : ''}'
                        '${call.labelTruncated ? '\nScope or callee label truncated' : ''}',
                      ),
                      onTap: () => widget.openSource(call.path, call.line),
                    ),
                ],
              ),
            ),
    ],
  );
}
