import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:nexus_flutter/features/code/application/code_providers.dart';
import 'package:nexus_flutter/features/code/presentation/upload_repository_dialog.dart';

class RepositoriesScreen extends ConsumerWidget {
  const RepositoriesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) => Scaffold(
    appBar: AppBar(
      title: const Text('Repositories'),
      actions: [
        IconButton(
          tooltip: 'Refresh repositories',
          onPressed: () => ref.invalidate(repositoriesProvider),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(24),
      children: [
        const Text(
          'Read-only source snapshots. Python symbols; text search for Python, Dart, JavaScript and TypeScript. Graphs are not available yet.',
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: () => showDialog<void>(
            context: context,
            barrierDismissible: false,
            builder: (_) => const UploadRepositoryDialog(),
          ),
          icon: const Icon(Icons.upload_file),
          label: const Text('Import ZIP'),
        ),
        const SizedBox(height: 16),
        ref
            .watch(repositoriesProvider)
            .when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (_, _) => const Text(
                'Could not load repositories. Use Refresh to retry.',
              ),
              data: (items) => Column(
                children: [
                  if (items.isEmpty) const Text('No repository snapshots yet.'),
                  for (final item in items)
                    ListTile(
                      title: Text(item.name),
                      subtitle: Text('${item.fileCount} source files'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => context.push('/repositories/${item.id}'),
                    ),
                  if (items.length == 20)
                    const Text('Showing the 20 most recent snapshots.'),
                ],
              ),
            ),
      ],
    ),
  );
}
