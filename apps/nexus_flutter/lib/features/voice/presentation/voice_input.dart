import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/voice/application/voice_controller.dart';
import 'package:nexus_flutter/features/voice/domain/voice_state.dart';

class VoiceInput extends ConsumerStatefulWidget {
  const VoiceInput({
    super.key,
    required this.onTranscript,
    this.enabled = true,
  });
  final ValueChanged<String> onTranscript;
  final bool enabled;

  @override
  ConsumerState<VoiceInput> createState() => _VoiceInputState();
}

class _VoiceInputState extends ConsumerState<VoiceInput>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if ({
      AppLifecycleState.paused,
      AppLifecycleState.hidden,
      AppLifecycleState.detached,
    }.contains(state)) {
      unawaited(ref.read(voiceControllerProvider.notifier).cancel());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(voiceControllerProvider);
    final controller = ref.read(voiceControllerProvider.notifier);
    ref.listen(voiceControllerProvider, (previous, next) {
      if (next.phase == VoicePhase.review && previous != next) {
        widget.onTranscript(next.text);
      }
    });
    final label = switch (state.phase) {
      VoicePhase.idle => 'Speak a goal. Audio goes to your NEXUS server.',
      VoicePhase.connecting => 'Connecting and requesting microphone access…',
      VoicePhase.recording =>
        'Recording (up to ${state.maxSeconds}s). Tap Done to transcribe.',
      VoicePhase.transcribing => 'Transcribing… You can still cancel.',
      VoicePhase.review =>
        state.isMock
            ? 'Demo transcript — not speech recognition. Review before starting.'
            : 'Transcript ready. Edit it below, then start your mission.',
      VoicePhase.error => state.message ?? 'Voice input failed.',
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 8,
          children: [
            if (!state.isBusy)
              OutlinedButton.icon(
                onPressed: widget.enabled ? controller.start : null,
                icon: const Icon(Icons.mic_none_rounded),
                label: const Text('Speak'),
              ),
            if (state.phase == VoicePhase.recording)
              FilledButton.icon(
                onPressed: controller.finish,
                icon: const Icon(Icons.stop_rounded),
                label: const Text('Done recording'),
              ),
            if (state.isBusy)
              TextButton(
                onPressed: controller.cancel,
                child: const Text('Cancel voice'),
              ),
          ],
        ),
        Semantics(
          liveRegion: true,
          child: Text(label, style: Theme.of(context).textTheme.bodySmall),
        ),
      ],
    );
  }
}
