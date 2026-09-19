/// Memory screen: displays categorized long-term memories with confidence bars.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/memory/application/memory_controller.dart';
import 'package:nexus_flutter/features/memory/domain/nexus_memory.dart';

class MemoryScreen extends ConsumerWidget {
  const MemoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(memoryControllerProvider);
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
                          'Memory',
                          style: Theme.of(context).textTheme.headlineLarge,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'What NEXUS remembers about you',
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
                  IconButton.outlined(
                    icon: const Icon(Icons.refresh_rounded),
                    tooltip: 'Refresh',
                    onPressed: () =>
                        ref.read(memoryControllerProvider.notifier).refresh(),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              state.when(
                loading: () => const Center(
                  child: Padding(
                    padding: EdgeInsets.all(48),
                    child: CircularProgressIndicator(),
                  ),
                ),
                error: (err, _) => _ErrorCard(message: err.toString()),
                data: (mems) => mems.isEmpty
                    ? const _EmptyState()
                    : _MemoryList(memories: mems),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------

class _MemoryList extends StatelessWidget {
  const _MemoryList({required this.memories});

  final List<NexusMemory> memories;

  @override
  Widget build(BuildContext context) {
    // Group by category
    final grouped = <MemoryCategory, List<NexusMemory>>{};
    for (final m in memories) {
      grouped.putIfAbsent(m.category, () => []).add(m);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final entry in grouped.entries) ...[
          Padding(
            padding: const EdgeInsets.only(bottom: 8, top: 4),
            child: Text(
              _categoryLabel(entry.key),
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                color: _categoryColor(entry.key),
                letterSpacing: 1.2,
              ),
            ),
          ),
          for (final m in entry.value) _MemoryCard(memory: m),
          const SizedBox(height: 16),
        ],
      ],
    );
  }

  static String _categoryLabel(MemoryCategory c) => switch (c) {
    MemoryCategory.userPreference => 'PREFERENCES',
    MemoryCategory.userGoal => 'GOALS',
    MemoryCategory.userFact => 'FACTS',
    MemoryCategory.projectContext => 'PROJECTS',
    MemoryCategory.learningState => 'LEARNING',
    MemoryCategory.taskContext => 'TASKS',
  };
}

Color _categoryColor(MemoryCategory c) => switch (c) {
  MemoryCategory.userPreference => const Color(0xFF42D6FF),
  MemoryCategory.userGoal => const Color(0xFFFFC857),
  MemoryCategory.userFact => const Color(0xFF54E6A5),
  MemoryCategory.projectContext => const Color(0xFFBB86FC),
  MemoryCategory.learningState => const Color(0xFFFF9A3C),
  MemoryCategory.taskContext => const Color(0xFFFF6B7A),
};

class _MemoryCard extends ConsumerWidget {
  const _MemoryCard({required this.memory});

  final NexusMemory memory;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final color = _categoryColor(memory.category);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    memory.content,
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: const Icon(Icons.edit_outlined, size: 18),
                  tooltip: 'Edit memory',
                  onPressed: () => _showAction(context, deleting: false),
                  visualDensity: VisualDensity.compact,
                ),
                IconButton(
                  icon: const Icon(Icons.delete_outline, size: 18),
                  tooltip: 'Forget',
                  onPressed: () => _showAction(context, deleting: true),
                  visualDensity: VisualDensity.compact,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: memory.confidence,
                      color: color,
                      backgroundColor: color.withValues(alpha: 0.15),
                      minHeight: 4,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '${(memory.confidence * 100).round()}%',
                  style: Theme.of(
                    context,
                  ).textTheme.labelSmall?.copyWith(color: color),
                ),
                const SizedBox(width: 12),
                Text(
                  memory.source,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _showAction(
    BuildContext context, {
    required bool deleting,
  }) async {
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _MemoryActionDialog(memory: memory, deleting: deleting),
    );
  }
}

class _MemoryActionDialog extends ConsumerStatefulWidget {
  const _MemoryActionDialog({required this.memory, required this.deleting});
  final NexusMemory memory;
  final bool deleting;

  @override
  ConsumerState<_MemoryActionDialog> createState() =>
      _MemoryActionDialogState();
}

class _MemoryActionDialogState extends ConsumerState<_MemoryActionDialog> {
  late final _text = TextEditingController(text: widget.memory.content);
  bool _pending = false;
  String? _error;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_pending) return;
    final content = _text.text.trim();
    if (!widget.deleting && (content.isEmpty || content.runes.length > 500)) {
      setState(() => _error = 'Enter 1 to 500 characters.');
      return;
    }
    setState(() {
      _pending = true;
      _error = null;
    });
    try {
      final controller = ref.read(memoryControllerProvider.notifier);
      if (widget.deleting) {
        await controller.delete(widget.memory.id);
      } else {
        await controller.edit(widget.memory.id, content);
      }
      if (mounted) Navigator.of(context).pop();
    } catch (_) {
      if (mounted) {
        setState(() {
          _pending = false;
          _error =
              'Could not save this change. Your draft is still here. Try again.';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_pending,
    child: AlertDialog(
      title: Text(widget.deleting ? 'Forget this memory?' : 'Edit memory'),
      content: SizedBox(
        width: 420,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (widget.deleting)
              Text(widget.memory.content)
            else ...[
              TextField(
                controller: _text,
                readOnly: _pending,
                minLines: 2,
                maxLines: 5,
                decoration: const InputDecoration(
                  labelText: 'Memory content',
                  helperText: 'Up to 500 characters',
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                'Saving marks this memory as user-confirmed with 100% confidence.',
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _pending ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _pending ? null : _submit,
          child: Text(
            _pending
                ? 'Saving...'
                : widget.deleting
                ? 'Forget'
                : 'Save memory',
          ),
        ),
      ],
    ),
  );
}

// ---------------------------------------------------------------------------

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(32),
        child: Column(
          children: [
            Icon(Icons.psychology_rounded, size: 48),
            SizedBox(height: 12),
            Text(
              'No memories yet.',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            SizedBox(height: 6),
            Text(
              'As NEXUS completes missions, it will extract and store '
              'important facts, preferences, and context here.',
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
