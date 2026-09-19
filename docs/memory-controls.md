# Memory controls and workspace alignment

The Memory screen now supports editing saved text as well as confirmed deletion.
Open **Memory**, press **Edit memory**, change the text, and press **Save memory**.
An edit accepts 1–500 nonblank Unicode characters, trims surrounding whitespace,
and marks the memory as user-confirmed (`source=user`, `confidence=1.0`). Its ID,
category, originating run ID, and creation time are retained; update time changes.

The dialog prevents duplicate submission while saving. Failed edits keep the
draft available for retry and display a sanitized error. Forgetting still
requires confirmation; a failed deletion does not remove the displayed memory.
Successful changes reload the server list through Riverpod invalidation so old
refresh requests cannot overwrite the new list.

## API

All memory routes use a bounded `user_id` query parameter, defaulting to `local`,
the same workspace label used by mission creation and Flutter.

- `POST /api/v1/memories`: existing creation body (category, content, confidence).
- `GET /api/v1/memories`: optional category, confidence threshold in `[0,1]`, and
  limit in `[1,100]` (default 50). Filtering happens before limiting results.
- `PATCH /api/v1/memories/{id}`: body `{"content":"Corrected preference"}`.
- `DELETE /api/v1/memories/{id}`: returns 204 after successful removal.

Missing and other-workspace targets both return 404 for edits and deletions.
Repository reads and mutations require an explicit workspace label, including
SQL mutation predicates. SQL content edits lock the selected row on PostgreSQL.
Concurrent edits use last-successful-write semantics; there is no version-token
conflict UI yet.

## Compatibility and data preservation

Previously memory routes hard-coded `default`, while mission extraction saved
under the run's workspace (normally `local`). This prevented the default app
view from showing those extracted memories.

Existing `default` records are **not moved, merged, or deleted**. Access them
with `GET /api/v1/memories?user_id=default`, and use the same query parameter on
edit/delete requests. Older API clients relying on the old default must specify
`user_id=default` explicitly. The Flutter screen currently shows only `local`;
a workspace picker and migration interface remain future work.

PostgreSQL keeps its existing JSONB column; SQLite uses JSON for repository
regression tests. No existing table or data migration is required.

## Verification and limits

94 backend tests and 51 Flutter tests passed, including memory API validation,
owner isolation, legacy workspace access, edit provenance, copy isolation,
filter-before-limit behavior, SQL database reopen, dialog confirmation, pending
submission, failed writes, and retry. Backend lint, strict typing, Flutter
analysis, and the release web build also passed.

Database-reopen tests use SQLite. PostgreSQL runtime checks and browser visual
QA were not rerun for this slice. Workspace labels remain **not authentication**;
this application is intended for trusted local use, not multi-tenant deployment.
User confirmation is not proof that memory text is safe to execute.

This closes the editing-control gap, not all Phase 4 acceptance criteria.
Automatic relevant-memory retrieval during planning, stronger extraction policy,
and broader real-model evaluation remain open. Voice hardware verification and
Phases 7–8 also remain unfinished.
