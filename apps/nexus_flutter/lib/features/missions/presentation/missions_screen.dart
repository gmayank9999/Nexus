import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/missions/application/mission_controller.dart';
import 'package:nexus_flutter/features/missions/domain/mission_event.dart';
import 'package:nexus_flutter/features/missions/domain/mission_run.dart';

class MissionsScreen extends ConsumerWidget {
  const MissionsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final feed = ref.watch(missionControllerProvider);
    return CustomScrollView(
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(24, 28, 24, 96),
          sliver: SliverList.list(
            children: [
              Text(
                'Missions',
                style: Theme.of(context).textTheme.headlineLarge,
              ),
              const SizedBox(height: 6),
              Text(
                'Live agent activity and decisions',
                style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 24),
              if (feed.run == null)
                const _EmptyTimeline()
              else
                feed.run!.when(
                  loading: () => const Center(
                    child: Padding(
                      padding: EdgeInsets.all(48),
                      child: CircularProgressIndicator(),
                    ),
                  ),
                  error: (error, _) => _ErrorCard(message: error.toString()),
                  data: (run) => _MissionDetails(run: run, feed: feed),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _MissionDetails extends ConsumerWidget {
  const _MissionDetails({required this.run, required this.feed});

  final MissionRun run;
  final MissionFeedState feed;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final terminal = {
      MissionRunStatus.completed,
      MissionRunStatus.failed,
      MissionRunStatus.cancelled,
    }.contains(run.status);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _RunSummary(run: run),
        if (run.status == MissionRunStatus.waitingForApproval) ...[
          const SizedBox(height: 16),
          _ApprovalCard(pending: feed.actionPending),
        ],
        if (feed.streamError != null) ...[
          const SizedBox(height: 12),
          _ErrorCard(message: feed.streamError!),
        ],
        if (!terminal) ...[
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: feed.actionPending
                ? null
                : () => ref.read(missionControllerProvider.notifier).cancel(),
            icon: const Icon(Icons.stop_circle_outlined),
            label: const Text('Cancel mission'),
          ),
        ],
        if (run.steps.isNotEmpty) ...[
          const SizedBox(height: 28),
          Text('Plan', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          for (var index = 0; index < run.steps.length; index++)
            _PlanStepTile(
              step: run.steps[index],
              completed: index < run.currentStep,
              active: index == run.currentStep && !terminal,
            ),
        ],
        const SizedBox(height: 28),
        Text('Agent timeline', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        if (feed.events.isEmpty)
          Text(
            'Connecting to the event stream…',
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          )
        else
          for (var index = 0; index < feed.events.length; index++)
            _EventTile(
              event: feed.events[index],
              isLast: index == feed.events.length - 1,
            ),
      ],
    );
  }
}

class _RunSummary extends StatelessWidget {
  const _RunSummary({required this.run});

  final MissionRun run;

  @override
  Widget build(BuildContext context) {
    final completed = run.status == MissionRunStatus.completed;
    final failed = {
      MissionRunStatus.failed,
      MissionRunStatus.cancelled,
    }.contains(run.status);
    final color = completed
        ? const Color(0xFF54E6A5)
        : failed
        ? const Color(0xFFFF6B7A)
        : const Color(0xFF42D6FF);
    final progress = run.steps.isEmpty
        ? null
        : (run.currentStep / run.steps.length).clamp(0.0, 1.0);
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainer,
        border: Border.all(color: color.withValues(alpha: 0.35)),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  run.goal,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              _StatusPill(status: run.status, color: color),
            ],
          ),
          const SizedBox(height: 16),
          LinearProgressIndicator(
            value: completed ? 1 : progress,
            color: color,
          ),
          if (run.finalResponse != null || run.errorMessage != null) ...[
            const SizedBox(height: 14),
            Text(run.finalResponse ?? run.errorMessage!),
          ],
        ],
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.status, required this.color});

  final MissionRunStatus status;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(99),
      ),
      child: Text(
        status.name,
        style: Theme.of(context).textTheme.labelMedium?.copyWith(color: color),
      ),
    );
  }
}

class _ApprovalCard extends ConsumerWidget {
  const _ApprovalCard({required this.pending});

  final bool pending;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final controller = ref.read(missionControllerProvider.notifier);
    return Card(
      color: const Color(0xFFFFC857).withValues(alpha: 0.1),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Approval required',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 6),
            const Text('NEXUS paused before performing this action.'),
            const SizedBox(height: 14),
            Wrap(
              spacing: 10,
              children: [
                FilledButton.icon(
                  onPressed: pending ? null : controller.approve,
                  icon: const Icon(Icons.check_rounded),
                  label: const Text('Approve'),
                ),
                OutlinedButton.icon(
                  onPressed: pending ? null : controller.reject,
                  icon: const Icon(Icons.close_rounded),
                  label: const Text('Reject'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _PlanStepTile extends StatelessWidget {
  const _PlanStepTile({
    required this.step,
    required this.completed,
    required this.active,
  });

  final MissionStep step;
  final bool completed;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final color = completed
        ? const Color(0xFF54E6A5)
        : active
        ? const Color(0xFF42D6FF)
        : Theme.of(context).colorScheme.onSurfaceVariant;
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        completed
            ? Icons.check_circle
            : active
            ? Icons.radio_button_checked
            : Icons.radio_button_unchecked,
        color: color,
      ),
      title: Text(step.title),
      subtitle: step.description.isEmpty ? null : Text(step.description),
      trailing: Text(step.tool, style: Theme.of(context).textTheme.labelSmall),
    );
  }
}

class _EventTile extends StatelessWidget {
  const _EventTile({required this.event, required this.isLast});

  final MissionEvent event;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    final color = _eventColor(event.type);
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            width: 28,
            child: Column(
              children: [
                Container(
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                    color: color,
                    shape: BoxShape.circle,
                  ),
                ),
                if (!isLast)
                  Expanded(
                    child: Container(
                      width: 2,
                      color: color.withValues(alpha: 0.25),
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(left: 8, bottom: 10),
              child: Card(
                margin: EdgeInsets.zero,
                child: ExpansionTile(
                  shape: const Border(),
                  title: Text(_eventTitle(event.type)),
                  subtitle: Text('Event ${event.sequence}'),
                  children: event.payload.isEmpty
                      ? const []
                      : [
                          Padding(
                            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                            child: SelectableText(
                              const JsonEncoder.withIndent(
                                '  ',
                              ).convert(_redact(event.payload)),
                            ),
                          ),
                        ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyTimeline extends StatelessWidget {
  const _EmptyTimeline();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(32),
        child: Column(
          children: [
            Icon(Icons.timeline_rounded, size: 40),
            SizedBox(height: 12),
            Text('Start a mission from Home to see its live timeline.'),
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

String _eventTitle(String type) => switch (type) {
  'run_created' => 'Mission created',
  'run_started' => 'Agent started',
  'planning_started' => 'Planning goal',
  'plan_created' => 'Plan created',
  'step_started' => 'Step started',
  'tool_requested' => 'Tool selected',
  'tool_started' => 'Tool running',
  'tool_completed' => 'Tool completed',
  'tool_failed' => 'Tool failed',
  'approval_required' => 'Waiting for approval',
  'approval_received' => 'Approval response received',
  'replanning_started' => 'Updating plan',
  'agent_message' => 'Agent response',
  'run_completed' => 'Mission completed',
  'run_failed' => 'Mission failed',
  'run_cancelled' => 'Mission cancelled',
  'status_changed' => 'Status changed',
  _ => type.replaceAll('_', ' '),
};

Color _eventColor(String type) {
  if (type == 'run_completed' || type == 'tool_completed') {
    return const Color(0xFF54E6A5);
  }
  if (type == 'run_failed' || type == 'tool_failed') {
    return const Color(0xFFFF6B7A);
  }
  if (type == 'approval_required') {
    return const Color(0xFFFFC857);
  }
  return const Color(0xFF42D6FF);
}

Object? _redact(Object? value) {
  if (value is Map) {
    return value.map((key, child) {
      final normalized = key.toString().toLowerCase();
      final sensitive = const [
        'key',
        'token',
        'password',
        'secret',
      ].any(normalized.contains);
      return MapEntry(
        key.toString(),
        sensitive ? '[redacted]' : _redact(child),
      );
    });
  }
  if (value is List) {
    return value.map(_redact).toList(growable: false);
  }
  return value;
}
