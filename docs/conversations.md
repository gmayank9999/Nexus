# Follow-up missions

Phase 6 now supports explicit, persisted follow-up context for typed or reviewed
spoken goals. This is turn-based interaction, not full-duplex voice chat.

## Try it

1. Complete a mission from Home, for example `Create a task to study Flutter`.
2. Press **Follow up** on the result or a completed mission's detail page.
3. Home shows the selected goal. Type a new goal, or use Speak and review the
   transcript. Nothing is submitted just by selecting context or finishing audio.
4. Press **Start mission**. A new mission gets its own plan, events, cancellation,
   approval flow, tasks, and artifacts. Its detail page links to the previous run.
5. Use the context banner's close button to start without previous context.

With the mock LLM provider, ask exactly `What was the previous result?` to get a
labeled echo of the selected parent's reply. This fixture demonstrates context
transport; it is not a general conversational model. Other mock goals retain
their existing deterministic behavior. Real-provider conversational quality has
not been verified in this slice.

The selected context is consumed after successful submission, retained on a
request failure, and never silently attached to a later unrelated mission.
Unsaved drafts are in-memory UI state; they do not survive app restart.

## API and storage contract

`POST /api/v1/runs` accepts an optional `parent_run_id`:

```json
{
  "goal": "What was the previous result?",
  "user_id": "local",
  "parent_run_id": "run_..."
}
```

The server resolves the parent, checks that it belongs to the same workspace
label, and requires a completed run with a final response. Missing and
other-workspace parents both return `404 RUN_NOT_FOUND`. Non-completed parents
return `409 PARENT_RUN_NOT_COMPLETED`. Invalid IDs return validation errors.

The server snapshots the latest three ancestors in chronological order. Each
snapshot contains `run_id`, the first 2,000 Unicode characters of its goal, the
first 4,000 characters of its final response, and a `truncated` flag. Total goal
and reply text is at most 18,000 characters, plus JSON metadata. There is no
unbounded ancestry traversal. `context.conversation_truncated` flags a chain
that has lost text or older turns; the detail page discloses that limitation.

`parent_run_id` and `context.conversation` are stored in the existing run JSON.
No database-column migration is needed. Legacy runs load with empty context.
Snapshots survive SQL database reopen and do not change if the parent is later
updated. The `run_created` event records the parent ID without duplicating the
history text in event payloads.

Planner, executor, and replanner receive the same bounded snapshot. Earlier
tool observations, plans, traces, audio, approval decisions, and full artifact
bodies are not copied. A request needing omitted content still needs explicit
retrieval support; a short final reply is not a complete artifact snapshot.

## Boundaries

- Current goals remain explicit. Prior text is untrusted context, not a new
  instruction or authorization. Prompt guidance is not a complete injection
  defense; schema validation, registered tools, and existing runtime controls
  still apply.
- Workspace labels are **not authentication**. Existing run-by-ID endpoints
  are for trusted local use; do not expose this prototype as a multi-tenant API.
- Context is persisted as text and sent to the configured backend LLM provider.
  Selecting a cloud provider therefore sends these excerpts to that provider.
- Voice still uses bounded utterances, final transcription, review, and explicit
  submission. Microphone and speech-output limits are unchanged.

## Verification

This slice passed 78 backend tests and 46 Flutter tests, backend lint/type checks,
Flutter analysis, and the release web build. Added coverage includes workspace
isolation, non-completed parents, bounded chains, legacy data, SQL reopen,
planner/executor/replanner payloads, mock follow-up execution, API serialization,
typed and spoken submission, parent navigation, context removal, failure recovery,
and stale-draft protection.

SQL reopen uses SQLite in automated tests; PostgreSQL restart was not rerun for
this slice. Flutter tests use injected APIs/audio and the widget test runner,
not a real microphone, speaker, or browser speech engine. See the existing
[browser/Windows verification limits](speech-output.md#verification).

Phase 6 remains in progress: real-device/model acceptance, safe native Windows
speech output, incremental recognition/full-duplex interaction, and self-hosted
speech output remain open. Phase 7 now has a [repository import backend](code-intelligence.md);
its graphs and Phase 8 remain unfinished. The source browser and read-only agent tools are now available. Earlier
memory/RAG acceptance gaps remain in [mission notes](missions.md#remaining-work).

## Implementation locations

- Backend: `app/agent/{models,runtime,planner,executor}.py`, agent prompts,
  run request/route, and the mock provider.
- Backend regression coverage: `tests/test_conversation.py`.
- Flutter: mission API/model/controllers, Home, and mission details.
- Flutter regression coverage: follow-up, navigation, Home, and mission tests.
