import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:nexus_flutter/features/outputs/data/outputs_api.dart';

class OutputsScreen extends ConsumerWidget {
  const OutputsScreen({required this.showTasks, this.runId, super.key});
  final bool showTasks;
  final String? runId;

  @override
  Widget build(BuildContext context, WidgetRef ref) => Scaffold(
    appBar: AppBar(
      title: Text(showTasks ? 'Tasks' : 'Artifacts'),
      leading: IconButton(
        icon: const Icon(Icons.arrow_back),
        onPressed: () {
          if (context.canPop()) {
            context.pop();
          } else {
            context.go('/missions');
          }
        },
      ),
    ),
    body: RefreshIndicator(
      onRefresh: () async {
        if (showTasks) {
          ref.invalidate(tasksProvider(runId));
          await ref.read(tasksProvider(runId).future);
        } else {
          ref.invalidate(artifactsProvider(runId));
          await ref.read(artifactsProvider(runId).future);
        }
      },
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(24),
        children: [
          Text(
            runId == null
                ? 'Across all your missions'
                : 'Saved by this mission',
          ),
          const SizedBox(height: 20),
          if (showTasks)
            ref
                .watch(tasksProvider(runId))
                .when(
                  loading: () =>
                      const Center(child: CircularProgressIndicator()),
                  error: (_, _) => _Retry(
                    onRetry: () => ref.invalidate(tasksProvider(runId)),
                  ),
                  data: (tasks) => tasks.isEmpty
                      ? const Text('No tasks yet.')
                      : Column(
                          children: [
                            for (final task in tasks) _TaskTile(task: task),
                          ],
                        ),
                )
          else
            ref
                .watch(artifactsProvider(runId))
                .when(
                  loading: () =>
                      const Center(child: CircularProgressIndicator()),
                  error: (_, _) => _Retry(
                    onRetry: () => ref.invalidate(artifactsProvider(runId)),
                  ),
                  data: (artifacts) => artifacts.isEmpty
                      ? const Text('No artifacts yet.')
                      : Column(
                          children: [
                            for (final artifact in artifacts)
                              _ArtifactTile(artifact: artifact),
                          ],
                        ),
                ),
        ],
      ),
    ),
  );
}

class _TaskTile extends ConsumerStatefulWidget {
  const _TaskTile({required this.task});
  final MissionTask task;
  @override
  ConsumerState<_TaskTile> createState() => _TaskTileState();
}

class _TaskTileState extends ConsumerState<_TaskTile> {
  bool _saving = false;

  Future<void> _toggle(bool? value) async {
    setState(() => _saving = true);
    try {
      await ref
          .read(outputsApiProvider)
          .setCompleted(widget.task.id, value ?? false);
      ref.invalidate(tasksProvider);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Could not update the task. Please retry.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Card(
    child: Column(
      children: [
        CheckboxListTile(
          value: widget.task.completed,
          onChanged: _saving ? null : _toggle,
          title: Text(widget.task.title),
          subtitle: widget.task.description == null
              ? null
              : Text(widget.task.description!),
        ),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton(
            onPressed: () => context.go('/missions/${widget.task.runId}'),
            child: const Text('Open mission'),
          ),
        ),
      ],
    ),
  );
}

class _ArtifactTile extends StatelessWidget {
  const _ArtifactTile({required this.artifact});
  final MissionArtifact artifact;

  @override
  Widget build(BuildContext context) => Card(
    child: ExpansionTile(
      leading: Icon(switch (artifact.type) {
        'checklist' => Icons.checklist,
        'study_guide' => Icons.school_outlined,
        'plan' => Icons.route_outlined,
        'architecture_diagram' => Icons.account_tree_outlined,
        'code_explanation' => Icons.code,
        _ => Icons.article_outlined,
      }),
      title: Text(artifact.title),
      subtitle: Text(artifact.typeLabel),
      childrenPadding: const EdgeInsets.all(20),
      expandedCrossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (artifact.type == 'checklist')
          for (final line
              in artifact.content
                  .split('\n')
                  .where((line) => line.trim().isNotEmpty))
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.check_box_outline_blank, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      line.replaceFirst(
                        RegExp(r'^\s*[-*]\s*(\[[ xX]\]\s*)?'),
                        '',
                      ),
                    ),
                  ),
                ],
              ),
            )
        else
          SelectableText(
            artifact.content,
            style: TextStyle(
              fontFamily:
                  const {
                    'architecture_diagram',
                    'code_explanation',
                  }.contains(artifact.type)
                  ? 'monospace'
                  : null,
              height: 1.5,
            ),
          ),
        const SizedBox(height: 12),
        TextButton(
          onPressed: () => context.go('/missions/${artifact.runId}'),
          child: const Text('Open mission'),
        ),
      ],
    ),
  );
}

class _Retry extends StatelessWidget {
  const _Retry({required this.onRetry});
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => Column(
    children: [
      const Text('Could not load saved outputs.'),
      TextButton(onPressed: onRetry, child: const Text('Retry')),
    ],
  );
}
