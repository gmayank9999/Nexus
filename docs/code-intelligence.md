# Code intelligence: repository snapshot foundation

Phase 7 now includes repository ingestion and a Flutter source browser.
Agent code tools, dependency/call graphs, and source-grounded flow explanations
are not implemented yet. This milestone does
not satisfy the full “Trace login flow” acceptance criterion.

## Import and inspect

In Flutter, open **Knowledge → Browse code repositories → Import ZIP**. Choose
a ZIP, review its filename and snapshot name, then press **Upload snapshot**.
Selecting a file does not send it to the server. The UI checks the 5 MiB limit
before reading and again while collecting bytes; the backend remains authoritative
for ZIP structure and indexing limits. There are no automatic upload retries.
If a request fails after a possible server commit, refresh before retrying to
avoid duplicate snapshots.

Open a snapshot to expand files and Python symbols. Search returns matching
path/line locations; selecting a match or symbol opens a plain-text source window
with its SHA-256. Source is never rendered as HTML. Windows are bounded to 200
lines / 20,000 characters, and a long line can be cut. “Next 200 lines” moves to
the next line window, not the remainder of a cut line. Clearing search returns
to browsing. Query/snapshot-keyed providers prevent late results from replacing
a newer selection.

The picker uses Flutter's [file_selector package](https://pub.dev/packages/file_selector).
Native file-dialog behavior and device permissions still require device testing.
The Knowledge document-upload placeholder is unchanged; this picker is currently
connected only to repository imports.

Upload a ZIP that you have reviewed for secrets. Example from PowerShell:

```powershell
curl.exe -F "file=@sample.zip" "http://localhost:8000/api/v1/repositories?name=Sample"
```

The response contains a repository ID. Available routes are:

- `GET /api/v1/repositories`: latest 20 snapshot summaries.
- `GET /api/v1/repositories/{id}/files`: file metadata, Python symbols/imports,
  parse-error flags, and excluded-file count; no source bodies.
- `GET /api/v1/repositories/{id}/file?path=src/app.py&start_line=1`: source window
  of up to 200 lines and 20,000 characters, with source hash and truncation flag.
- `GET /api/v1/repositories/{id}/search?query=login`: case-insensitive literal
  text search with at most 20 matches, each carrying path, line, source hash,
  and the first 300 characters of the matched line. Long-line excerpts may omit
  the matched substring; no syntax or semantic matching is implied.

All routes accept `user_id` (default `local`). A missing snapshot and a snapshot
in another workspace both return 404. Workspace labels are not authentication;
use this prototype only on trusted local infrastructure.

## Indexing behavior

Supported UTF-8 source extensions are `.py`, `.dart`, `.js`, `.jsx`, `.ts`, and
`.tsx`. Python's AST parser extracts class/function qualified names and import
module strings, with one-based source locations. Imports are syntax facts, not
resolved dependency edges. Method declarations currently use the `function`
kind with a class-qualified name. Conditional/nested definitions are indexed
syntactically, without claims about runtime reachability.

Invalid Python syntax remains available for text search with `parse_error=true`.
Other supported languages have text search only. Indexing never imports modules,
executes source, invokes a shell, downloads dependencies, or clones a remote URL.
Archives are inspected in memory and never extracted to filesystem paths.

Each successful import is an immutable snapshot stored in the existing SQL
database. Snapshot listing does not load stored source bodies. A new import
creates a new ID, even for identical content. There is no refresh, deletion,
retention policy, or deduplication endpoint in this slice; avoid repeated imports
of large archives. The archive SHA-256 and each source-file SHA-256 provide
integrity identifiers, not a guarantee about source trustworthiness.

## Limits and exclusions

- ZIP payload: 5 MiB; declared uncompressed total: 10 MiB.
- At most 1,000 archive entries and 200 accepted source files.
- Each accepted source file: 256 KiB; at most 1,000 symbol/import records per
  Python file, with `index_truncated` disclosed when that ceiling is reached.
- Two indexing workers per API process. Cancelling an HTTP request does not
  release its indexing slot until its worker finishes. Requests cancelled during
  indexing do not subsequently save a snapshot. Cancellation after database
  commit does not undo that commit. There is no distributed admission controller.
- Traversal/absolute paths, backslashes, control characters, duplicate
  case-insensitive paths, symlinks/special entries, and encrypted entries are
  rejected. Only ZIP stored/deflated compression is accepted.
- Hidden path components and `node_modules`, `vendor`, `build`, `dist`,
  `__pycache__`, and `coverage` are excluded, as are unsupported extensions,
  invalid UTF-8, and NUL-containing content. Archive-wide entry and size budgets
  still include excluded entries.

Exclusions are not a secret scanner. Credentials in ordinary source files will
be persisted if uploaded. No source is sent to an LLM in this slice. Configure
request-body limits at the deployment proxy as well: multipart parsing/spooling
happens before the route's bounded read. Malicious source parsing is bounded by
input size and concurrency, but is not isolated in a sandboxed worker process.

## Verification

124 backend tests passed, including 20 new repository tests covering Python
locations, syntax-error fallback, exclusions, unsafe paths, symlinks, collisions,
upload/decompression/file/count limits, source lookup, search limits, ownership,
SQL reopen, and cancellation/admission behavior. Backend lint, formatting, and
strict typing pass. Persistence tests use SQLite; PostgreSQL and browser/device
runtime checks were not rerun for the backend slice.

The subsequent browser slice passed 60 Flutter tests, static analysis, formatting,
and a release web build. Added tests cover selection versus upload confirmation,
oversize/cancel handling, duplicate-submit prevention, failure disclosure, source
locations, literal source rendering, search limits, stale responses, bounded
XFile reads, and multipart/query serialization. Tests inject the picker/API;
they do not prove real native dialog or live browser-to-backend behavior. No
backend code changed in that slice. Windows builds remain subject to the existing
Visual Studio C++ prerequisite; browser visual QA and real-device acceptance are
still open.

The source tables are created by the existing schema initialization path. No
existing tables or user data are rewritten. General versioned migrations remain
future work.
