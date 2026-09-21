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

- **Documents/RAG (Phase 3):** real-model resume Q&A with verified answer citations,
  extraction/indexing resource hardening and broader format coverage.
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

## Inspecting retrieved document sources

Tap an indexed document in Knowledge to browse its extracted chunks. Completed
mission details also show **Retrieved sources** links for structured `search_files`
results. Links are deduplicated and capped at 50; they are not created by parsing
model-written prose, and they do not prove that an answer is supported by the source.

The viewer opens the exact cited chunk, then offers previous/next navigation.
It displays document/chunk IDs, available page/section metadata, and plain text.
HTML and Markdown are not executed or rendered. Original file layout is not
preserved; chunks may overlap and missing page metadata is explicitly disclosed.

API: `GET /api/v1/documents/{id}/source?chunk_id=<id>` or `?chunk_index=0`.
An explicit chunk ID takes precedence over the index. Each response returns one
chunk, capped at 20,000 text characters with a truncation flag, and never returns
embeddings. Document ownership is checked before chunk lookup. Missing/deleted
and other-workspace documents return 404; a document not yet indexed returns 409.
SQL lookup selects one chunk without loading the document's other chunks or vectors.

Retrieval now labels the SQL document ID column explicitly so cited chunk IDs
remain distinct from their parent document IDs. The document JSON column uses a
SQLite-compatible variant for tests while retaining PostgreSQL JSONB; no existing
tables or user data are migrated.

Source-inspection verification: 194 backend tests and 73 Flutter tests passed,
with backend lint/formatting/typing and Flutter analysis clean. Tests cover exact
citation lookup, text limits, pending/deleted/other-workspace sources, foreign
chunk rejection, SQL citation identity, deduplicated links, plain-text rendering,
paging, and sanitized retry behavior. SQL tests use SQLite; live PostgreSQL,
real-model citation accuracy, native devices, and browser visual QA remain open.
The updated release web build passed with the existing CupertinoIcons warning.
