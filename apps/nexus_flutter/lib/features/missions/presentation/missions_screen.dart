import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:nexus_flutter/features/missions/application/mission_controller.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';

final missionHistoryProvider = FutureProvider.autoDispose<List<MissionRun>>((
  ref,
) {
  final timer = Timer(const Duration(seconds: 5), ref.invalidateSelf);
  ref.onDispose(timer.cancel);
  return ref.watch(missionApiProvider).listMissions();
});

class MissionsScreen extends ConsumerWidget {
  const MissionsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final missions = ref.watch(missionHistoryProvider);
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(missionHistoryProvider);
        await ref.read(missionHistoryProvider.future);
      },
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(24, 28, 24, 96),
        children: [
          Text('Missions', style: Theme.of(context).textTheme.headlineLarge),
          const SizedBox(height: 8),
          const Text('Your goals, progress, and saved results.'),
          const SizedBox(height: 20),
          Wrap(
            spacing: 12,
            runSpacing: 8,
            children: [
              FilledButton.icon(
                onPressed: () => context.go('/home'),
                icon: const Icon(Icons.add),
                label: const Text('New mission'),
              ),
              OutlinedButton.icon(
                onPressed: () => context.push('/tasks'),
                icon: const Icon(Icons.checklist),
                label: const Text('Tasks'),
              ),
              OutlinedButton.icon(
                onPressed: () => context.push('/artifacts'),
                icon: const Icon(Icons.article_outlined),
                label: const Text('Artifacts'),
              ),
            ],
          ),
          const SizedBox(height: 24),
          missions.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (_, _) => Column(
              children: [
                const Text('Could not load missions. Check your connection.'),
                TextButton(
                  onPressed: () => ref.invalidate(missionHistoryProvider),
                  child: const Text('Retry'),
                ),
              ],
            ),
            data: (runs) => runs.isEmpty
                ? const Padding(
                    padding: EdgeInsets.all(32),
                    child: Text(
                      'No missions yet. Start with a goal from Home.',
                    ),
                  )
                : Column(
                    children: [for (final run in runs) _MissionCard(run: run)],
                  ),
          ),
        ],
      ),
    );
  }
}

class _MissionCard extends StatelessWidget {
  const _MissionCard({required this.run});
  final MissionRun run;

  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.only(bottom: 14),
    child: InkWell(
      borderRadius: BorderRadius.circular(12),
      onTap: () => context.go('/missions/${run.id}'),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(run.goal, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 10),
            Text(
              '${run.statusLabel} · ${run.currentStep}/${run.steps.length} steps',
            ),
            const SizedBox(height: 12),
            LinearProgressIndicator(value: run.progress),
            if (run.finalResponse != null) ...[
              const SizedBox(height: 12),
              Text(
                run.finalResponse!,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ],
        ),
      ),
    ),
  );
}
