import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:nexus_flutter/features/missions/application/mission_controller.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';
import 'package:nexus_flutter/features/system_status/application/system_health_provider.dart';
import 'package:nexus_flutter/features/system_status/domain/system_health.dart';
import 'package:nexus_flutter/features/voice/application/voice_controller.dart';
import 'package:nexus_flutter/features/voice/presentation/spoken_reply.dart';
import 'package:nexus_flutter/features/voice/presentation/voice_input.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = Theme.of(context).colorScheme;
    return RefreshIndicator(
      onRefresh: () => ref.refresh(systemHealthProvider.future),
      child: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(24, 28, 24, 96),
            sliver: SliverList.list(
              children: [
                Text(
                  'NEXUS',
                  style: Theme.of(context).textTheme.displaySmall?.copyWith(
                    color: colors.primary,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 8,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Agentic AI Operating System',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: colors.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 36),
                const _CommandCard(),
                const SizedBox(height: 32),
                const _SectionTitle(
                  title: 'Active missions',
                  subtitle: 'Your autonomous workflows will appear here',
                ),
                const SizedBox(height: 14),
                const _MissionResult(),
                const SizedBox(height: 32),
                const _SectionTitle(
                  title: 'System status',
                  subtitle: 'Pull down to run the checks again',
                ),
                const SizedBox(height: 14),
                const _SystemStatusGrid(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _CommandCard extends ConsumerStatefulWidget {
  const _CommandCard();

  @override
  ConsumerState<_CommandCard> createState() => _CommandCardState();
}

class _CommandCardState extends ConsumerState<_CommandCard> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _startMission() async {
    await ref.read(missionControllerProvider.notifier).start(_controller.text);
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final mission = ref.watch(missionControllerProvider).run;
    final isLoading = mission?.isLoading == true;
    final voiceBusy = ref.watch(voiceControllerProvider).isBusy;
    final canSubmit =
        _controller.text.trim().isNotEmpty && !isLoading && !voiceBusy;
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: colors.surfaceContainer,
        border: Border.all(color: colors.primary.withValues(alpha: 0.28)),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: colors.primary.withValues(alpha: 0.08),
            blurRadius: 28,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'What do you want to accomplish?',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 16),
          VoiceInput(
            enabled: !isLoading,
            onTranscript: (text) => setState(() {
              _controller.text = text;
              _controller.selection = TextSelection.collapsed(
                offset: text.length,
              );
            }),
          ),
          const SizedBox(height: 12),
          TextField(
            readOnly: voiceBusy,
            controller: _controller,
            minLines: 2,
            maxLines: 4,
            onChanged: (_) => setState(() {}),
            onSubmitted: canSubmit ? (_) => _startMission() : null,
            decoration: const InputDecoration(
              hintText: 'Prepare me for a Flutter interview in 10 days…',
              prefixIcon: Padding(
                padding: EdgeInsets.only(bottom: 28),
                child: Icon(Icons.auto_awesome_outlined),
              ),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              IconButton.filledTonal(
                onPressed: null,
                tooltip: 'Documents arrive in a later phase',
                icon: const Icon(Icons.attach_file_rounded),
              ),
              const Spacer(),
              FilledButton.icon(
                onPressed: canSubmit ? _startMission : null,
                icon: isLoading
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.arrow_forward_rounded),
                label: Text(isLoading ? 'Working…' : 'Start mission'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MissionResult extends ConsumerWidget {
  const _MissionResult();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(missionControllerProvider);
    final run = state.run;
    if (run == null) {
      return const _EmptyMissionsCard();
    }
    return run.when(
      loading: () => const _MissionStatusCard.loading(),
      error: (error, _) => _MissionStatusCard.error(error.toString()),
      data: (mission) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _MissionStatusCard.mission(mission),
          if (mission.status == MissionRunStatus.completed &&
              mission.finalResponse?.trim().isNotEmpty == true)
            SpokenReply(sourceId: mission.id, text: mission.finalResponse!),
          TextButton.icon(
            onPressed: () => context.go('/missions/${mission.id}'),
            icon: const Icon(Icons.timeline),
            label: const Text('Open mission details'),
          ),
        ],
      ),
    );
  }
}

class _MissionStatusCard extends StatelessWidget {
  const _MissionStatusCard._({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.color,
    this.steps = const [],
  });

  const _MissionStatusCard.loading()
    : this._(
        title: 'Agent is working',
        subtitle: 'Planning and executing the mission…',
        icon: Icons.auto_awesome,
        color: const Color(0xFF42D6FF),
      );

  factory _MissionStatusCard.error(String message) {
    return _MissionStatusCard._(
      title: 'Mission request failed',
      subtitle: message,
      icon: Icons.error_outline,
      color: const Color(0xFFFF6B7A),
    );
  }

  factory _MissionStatusCard.mission(MissionRun mission) {
    final completed = mission.status == MissionRunStatus.completed;
    final waiting = mission.status == MissionRunStatus.waitingForApproval;
    final failed = {
      MissionRunStatus.failed,
      MissionRunStatus.cancelled,
    }.contains(mission.status);
    final color = completed
        ? const Color(0xFF54E6A5)
        : waiting
        ? const Color(0xFFFFC857)
        : failed
        ? const Color(0xFFFF6B7A)
        : const Color(0xFF42D6FF);
    return _MissionStatusCard._(
      title: completed
          ? 'Mission completed'
          : waiting
          ? 'Approval required'
          : failed
          ? 'Mission ${mission.status.name}'
          : 'Mission in progress',
      subtitle:
          mission.finalResponse ??
          mission.errorMessage ??
          'Review the agent trace.',
      icon: completed
          ? Icons.check_circle_outline
          : waiting
          ? Icons.approval_outlined
          : failed
          ? Icons.error_outline
          : Icons.auto_awesome,
      color: color,
      steps: mission.steps,
    );
  }

  final String title;
  final String subtitle;
  final IconData icon;
  final Color color;
  final List<MissionStep> steps;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainer,
        border: Border.all(color: color.withValues(alpha: 0.35)),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            subtitle,
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          if (steps.isNotEmpty) ...[
            const SizedBox(height: 16),
            for (final step in steps)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    Icon(Icons.check_rounded, size: 18, color: color),
                    const SizedBox(width: 8),
                    Expanded(child: Text(step.title)),
                    Text(
                      step.tool,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ],
      ),
    );
  }
}

class _SystemStatusGrid extends ConsumerWidget {
  const _SystemStatusGrid();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final health = ref.watch(systemHealthProvider);
    return health.when(
      loading: () => const _StatusLayout(
        cards: [
          _StatusCard.loading('Agent runtime'),
          _StatusCard.loading('PostgreSQL'),
          _StatusCard.loading('Redis'),
        ],
      ),
      error: (_, _) => const _StatusLayout(
        cards: [
          _StatusCard.offline('Agent runtime'),
          _StatusCard.offline('PostgreSQL'),
          _StatusCard.offline('Redis'),
        ],
      ),
      data: (value) => _StatusLayout(
        cards: [
          _StatusCard(
            label: 'Agent runtime',
            state: value.api,
            detail: 'API v${value.version}',
          ),
          _StatusCard(label: 'PostgreSQL', state: value.postgres),
          _StatusCard(label: 'Redis', state: value.redis),
        ],
      ),
    );
  }
}

class _StatusLayout extends StatelessWidget {
  const _StatusLayout({required this.cards});

  final List<Widget> cards;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < 680) {
          return Column(
            children: cards
                .map(
                  (card) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: card,
                  ),
                )
                .toList(),
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: cards
              .map(
                (card) => Expanded(
                  child: Padding(
                    padding: const EdgeInsets.only(right: 10),
                    child: card,
                  ),
                ),
              )
              .toList(),
        );
      },
    );
  }
}

class _StatusCard extends StatelessWidget {
  const _StatusCard({
    required this.label,
    required this.state,
    this.detail,
    this.isLoading = false,
  });

  const _StatusCard.loading(String label)
    : this(label: label, state: ServiceState.offline, isLoading: true);

  const _StatusCard.offline(String label)
    : this(label: label, state: ServiceState.offline);

  final String label;
  final ServiceState state;
  final String? detail;
  final bool isLoading;

  @override
  Widget build(BuildContext context) {
    final isOnline = state == ServiceState.online;
    final statusColor = isLoading
        ? Theme.of(context).colorScheme.onSurfaceVariant
        : isOnline
        ? const Color(0xFF54E6A5)
        : Theme.of(context).colorScheme.error;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainer,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Row(
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(
              color: statusColor,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: statusColor.withValues(alpha: 0.45),
                  blurRadius: 10,
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 2),
                Text(
                  isLoading
                      ? 'Checking…'
                      : detail ?? (isOnline ? 'Online' : 'Unavailable'),
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(color: statusColor),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.title, required this.subtitle});

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 4),
        Text(
          subtitle,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}

class _EmptyMissionsCard extends StatelessWidget {
  const _EmptyMissionsCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 32, horizontal: 20),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(18),
      ),
      child: const Column(
        children: [
          Icon(Icons.route_outlined, size: 36),
          SizedBox(height: 12),
          Text('No active missions'),
        ],
      ),
    );
  }
}
