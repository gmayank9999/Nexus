import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nexus_flutter/features/voice/application/speech_controller.dart';
import 'package:nexus_flutter/features/voice/application/voice_controller.dart';

class SpokenReply extends ConsumerStatefulWidget {
  const SpokenReply({super.key, required this.sourceId, required this.text});
  final String sourceId;
  final String text;

  @override
  ConsumerState<SpokenReply> createState() => _SpokenReplyState();
}

class _SpokenReplyState extends ConsumerState<SpokenReply>
    with WidgetsBindingObserver {
  late final SpeechController _controller;

  @override
  void initState() {
    super.initState();
    _controller = ref.read(speechControllerProvider.notifier);
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didUpdateWidget(SpokenReply oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.sourceId != widget.sourceId ||
        oldWidget.text != widget.text) {
      _controller.release(oldWidget.sourceId);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if ({
      AppLifecycleState.paused,
      AppLifecycleState.hidden,
      AppLifecycleState.detached,
    }.contains(state)) {
      unawaited(_controller.stop(sourceId: widget.sourceId));
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller.release(widget.sourceId);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final speech = ref.watch(speechControllerProvider);
    final captureBusy = ref.watch(voiceControllerProvider).isBusy;
    final ownState = speech.sourceId == widget.sourceId;
    final speaking = ownState && speech.isBusy;
    final shortened = widget.text.trim().runes.length > maxSpokenCharacters;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextButton.icon(
          onPressed: speaking
              ? () => _controller.stop(sourceId: widget.sourceId)
              : captureBusy || widget.text.trim().isEmpty
              ? null
              : () => _controller.play(widget.sourceId, widget.text),
          icon: Icon(
            speaking ? Icons.stop_circle_outlined : Icons.volume_up_outlined,
          ),
          label: Text(
            speaking
                ? 'Stop reading'
                : shortened
                ? 'Read first $maxSpokenCharacters characters'
                : 'Read reply aloud',
          ),
        ),
        Text(
          'Uses your device/browser speech engine, which may process text online.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        if (ownState && speech.message != null)
          Semantics(
            liveRegion: true,
            child: Text(
              speech.message!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
      ],
    );
  }
}
