# Project status and remaining acceptance work

The implementation plan has **nine phases, numbered 0–8**. Implemented features
are not the same as completed acceptance criteria. This is a local development
application; workspace labels are not authentication.

## Working foundations

Repository/CI setup, provider abstractions, the bounded agent loop, approval and
cancellation controls, streamed mission history, persistent tasks/artifacts,
document extraction/retrieval, memory controls, voice input/read-aloud adapters,
and Python snapshot/code browsers are implemented. See the feature documents for
specific tests and caveats; this does not assert production readiness.

## Remaining work

- **Documents/RAG (Phase 3):** richer citation navigation, real-model resume Q&A
  acceptance, extraction/indexing resource hardening and broader format coverage.
  The upload picker and document/mission workspace mismatch are now fixed.
- **Memory (Phase 4):** automatic relevant-memory injection and broader
  extraction-policy/integration verification. Keyword retrieval is tool-selected.
- **Voice (Phase 6):** real microphone/local speech-model acceptance, safe native
  Windows playback, self-hosted output, and fuller incremental conversation.
- **Code intelligence (Phase 7):** general-language entry discovery for “Trace
  login flow,” stronger binding analysis, and real-model source-grounded acceptance.
  Current graphs contain explicit local/imported candidates, not verified runtime
  paths; dynamic dispatch, re-exports, closures, and shadowing remain limitations.
- **Autonomous missions (Phase 8):** persistent scheduling, notifications,
  automatic crash recovery, and long-running/distributed execution. Existing
  bounded multi-step execution and replanning do not complete this phase.
- **Release verification:** browser visual QA, real devices, Windows build
  prerequisites, current live PostgreSQL smoke tests, security/authentication
  design for non-local deployment, and migration/recovery practices.

## Document upload and search

In **Knowledge**, press **Upload**, choose a document, review its filename and
size, then confirm with **Upload selected document**. Selection does not upload.
PDF, TXT, MD and DOCX are accepted up to 20 MiB; both client and server limit
reads. Indexing runs after the server accepts the upload. Use **Refresh documents**
to inspect the latest status; no automatic upload retries or polling are added.
On an uncertain upload failure, refresh before retrying to avoid duplicates.

New document API requests default to workspace `local`, matching missions.
Existing `default` documents are neither migrated nor deleted; access them with
`?user_id=default` on list/get/delete/upload endpoints. Workspace IDs are validated
labels, not credentials or a security boundary for a hosted service.

Mock demo: upload `resume.txt`, wait until indexed, then submit
`Search documents for Flutter`. This performs actual workspace-scoped retrieval
and returns bounded excerpts with document/chunk references. It is not a verified
answer to arbitrary resume questions. The integration test uses deterministic
hash embeddings, not real-model semantic evaluation. Historical mission traces
can retain retrieved excerpts even after a document is deleted.

Verification for this update: 190 backend tests and 71 Flutter tests passed;
backend lint/formatting/strict typing and Flutter analysis passed. Upload tests
cover explicit confirmation, picker cancellation, duplicate-submit prevention,
failure disclosure, byte/type limits, workspace isolation, legacy workspace
access, and indexed upload-to-search citations. Native picker dialogs, live
browser-to-backend uploads, real models, and live PostgreSQL were not exercised.
The release web build passed with the existing CupertinoIcons font warning.
