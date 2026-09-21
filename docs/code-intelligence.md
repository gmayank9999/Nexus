# Code intelligence: repository snapshot foundation

Phase 7 now includes repository ingestion and a Flutter source browser.
Read-only agent code tools, a Python declared-import graph, and function-level
candidate flow inspection are available. Fully resolved call graphs and
validated runtime-flow explanations are not implemented yet. This milestone does
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
be persisted if uploaded. Import and browser endpoints do not send source to an
LLM. Agent code-tool excerpts may be sent to the configured LLM during later
execution/replanning and may enter follow-up context. Configure
request-body limits at the deployment proxy as well: multipart parsing/spooling
happens before the route's bounded read. Malicious source parsing is bounded by
input size and concurrency, but is not isolated in a sandboxed worker process.

## Verification

### Agent tools

The planner can select four read-only tools:

- `list_repositories`: up to 20 recent snapshots in the mission workspace.
- `search_code`: repository ID and literal query; up to 20 path/line excerpts,
  each bounded to 300 characters and carrying its source SHA-256.
- `find_symbol`: repository ID and name substring; up to 20 indexed Python
  declarations. Reports an incomplete index for non-Python, invalid, or capped
  files. This does not resolve references or calls.
- `read_file`: repository ID, exact stored path, and optional starting line;
  at most 200 lines/20,000 characters. This is not a general filesystem reader.

Arguments cannot override the mission workspace. Missing and other-workspace
snapshots both produce `REPOSITORY_NOT_FOUND`. Schema validation rejects blank
queries, oversized queries, invalid line numbers, and unexpected arguments.
Tool timeouts and permission checks are shared with other agent tools.

Try these goals in mock mode after importing a snapshot:

```text
List repositories
Search code in repo_<actual ID> for login
Find symbol in repo_<actual ID> for login
Call sites in repo_<actual ID>
Dependencies in repo_<actual ID>
Dependencies in repo_<actual ID> under src
Inspect flow in repo_<actual ID> at app.py::login
```

Replace the placeholder with an ID returned by the first goal or import API.
These explicit fixtures execute real repository reads and return cited excerpts
in the mission reply/timeline; they do not simulate general code understanding.
`read_file` is registered for model-selected plans but has no dedicated mock goal
fixture. No code is executed and the demo does not create tasks or artifacts.

Source/comments are untrusted context, not instructions or approval. Code-tool
observations remain persisted in mission history. Runs that invoke any of these
seven tools skip automatic personal-memory extraction so repository evidence is
not fed to the fact extractor. This applies to the invoking run, not arbitrary
later goals that manually quote source or reuse follow-up excerpts. Existing
stored memories and historical traces are not changed.

The agent-tool slice passed 136 backend tests, lint, formatting, and strict
typing. Added coverage includes tool registration/integration, source locations,
hashes, workspace isolation, invalid arguments, arbitrary-path rejection,
truncation, incomplete symbols, mock missions, and personal-memory extraction
suppression. No frontend code changed; real-model behavior and live PostgreSQL
checks were not rerun.

## Python dependency graph

`GET /api/v1/repositories/{id}/dependencies?source_root=src` returns a bounded
declared-module graph. The optional root is an exact relative directory inside
the snapshot, useful for ZIP wrappers or src layouts; it is never a disk path.
The registered read-only `dependency_graph` agent tool accepts `repository_id`
and optional `source_root`. The explicit mock goals above support both the ZIP
root and a supplied source root.

Edges include source path, import line, source hash, declared module, resolution,
and a local target when exactly one indexed module file or package initializer
matches. Relative imports use the importing file's package directory. Ambiguous,
out-of-root, and unresolved imports remain explicit; unresolved does not mean
external. Imported member names are not indexed: `from pkg import child` points
only to the declared `pkg`, while `from . import child` remains unresolved.
Namespace packages without initializers, dynamic imports, runtime path changes,
and call relationships are not inferred. Source is never imported or executed.

Results cap at 500 edges with truncation disclosure. Module labels cap at 300
characters with per-label flags. Non-Python, invalid, skipped, or capped indexing
is disclosed as incomplete. Workspace scoping and the automatic personal-memory
extraction exclusion also apply to this tool. Validated call-flow
explanations remain pending. This backend slice passed 150 tests; frontend,
real-model, and live PostgreSQL acceptance were not rerun.

### Browsing dependencies

Open a repository, expand **Python import dependencies**, optionally enter a
snapshot source root, and press **Load dependencies**. The view lists declared
imports with their source locations and local targets or unresolved reasons.
Tap an import to read its source line; the imported-module button opens a
resolved target. Incomplete indexes and capped results are disclosed. This is
an import list, not a runtime trace or an interactive node-layout visualization.
Loading is explicit, failures retain the root for retry, and requests are keyed
by repository and root to keep results scoped correctly. Native-device and live
browser-to-backend acceptance remain unverified.

The dependency-browser slice passed 62 Flutter tests, static analysis, and a
release web build (with the existing CupertinoIcons font warning).
Coverage includes explicit loading, source-root serialization, index warnings,
source/target navigation, and error retry without exposing server details.
No backend code changed in this slice.

## Python call-site evidence

New ZIP imports also index Python call expressions. The read-only
`GET /api/v1/repositories/{id}/calls` endpoint and `call_sites` agent tool return
up to 500 call sites with path, line, zero-based UTF-8 byte column, source hash,
lexical scope, and callee label. Each file also has a 500-call index cap; capped,
unsupported, invalid, or older indexes are explicitly incomplete. Names and
scope labels are bounded to 300 characters, with truncation disclosure.

This is syntactic evidence, **not a resolved call graph**. `client.save()` records
that expression, not the identity of the object or method at runtime. Subscript,
factory-result, and other dynamic callees remain explicitly unresolved. Aliases,
inheritance, rebinding, callbacks, implicit decorator calls, and execution order
are not resolved. Lexical scope does not imply execution context: decorators and
default arguments can run outside their enclosing function's execution. Call
arguments and literals are not included in labels, and source is never executed.

Stored snapshots remain immutable and compatible. Snapshots imported before this
feature need re-import to obtain call evidence; they are not silently reported
as complete empty call indexes. Workspace isolation and the personal-memory
extraction exclusion apply to this tool. It is available to model-selected plans
and through the explicit `Call sites in repo_<actual ID>` mock goal.

These mock inspection missions read the actual uploaded snapshot, return bounded
source-cited replies, and retain the complete bounded tool result in the mission
trace. They do not infer resolved call targets or execution order, and do not
implement a general natural-language flow explanation. Integration coverage
checks upload-to-mission results, reply limits, and personal-memory extraction
suppression for both call-site and dependency inspection.

The mock mission integration slice passed 162 backend tests, lint, formatting,
and strict typing. Frontend code was unchanged; real-model and live PostgreSQL
acceptance were not rerun.

In Flutter, expand **Python call sites** inside a repository and press
**Load call sites**. Each entry opens its cited source line. Dynamic expressions,
truncated labels, capped results, and incomplete indexes are explicitly labeled.
An empty index is not presented as proof that the repository contains no calls.
Loading and retries are explicit; failures do not expose raw server details.
This is a source-evidence list, not a resolved call-flow visualization.

The call-browser slice passed 64 Flutter tests, static analysis, formatting, and
a release web build (with the existing CupertinoIcons font warning). Tests cover
explicit loading, source navigation, dynamic/truncation/incomplete disclosures,
empty results, retries, and API serialization. No backend code changed. Live
browser-to-backend and native-device acceptance were not rerun.

This slice passed 157 backend tests, lint, formatting, and strict typing. Tests cover lexical
scopes, async/nested functions, dynamic expressions, source citations, budgets,
legacy snapshots, and API/tool workspace isolation. No frontend code changed;
real-model and live PostgreSQL checks were not rerun. Resolved call graphs and
the full source-grounded “Trace login flow” acceptance criterion remain open.

## Function-level candidate flow inspection

In Flutter, expand a source file and use a Python function's **Inspect flow**
button. The dialog groups outgoing call edges under function nodes. Click an
edge to read its call site or use **Read candidate declaration** to inspect a
possible target. The graph has explicit candidate, unresolved, ambiguous, and
limit labels; it is not presented as a verified execution trace. Classes and
duplicate qualified function names are rejected with a retryable message.

The API is `GET /api/v1/repositories/{id}/flow?path=app.py&symbol=login`.
The read-only `source_flow` agent tool accepts the same exact snapshot path and
qualified function name, plus optional `max_depth` (0–5, default 3). Mock mode
supports `Inspect flow in repo_<actual ID> at app.py::login`, producing a bounded
source-cited explanation and structured graph in the tool trace.

Traversal follows **same-file top-level function name candidates only**. It does
not resolve imports, closures, parameter/assignment shadowing, decorators,
inheritance, or dynamic dispatch. A name match remains a hypothesis even when
there is just one declaration. Attribute and dynamic calls remain unresolved;
duplicate declarations are ambiguous. Scope attribution is lexical, including
default/decorator expressions, not a statement about when those calls run.
Recursive links are retained without repeatedly expanding their nodes.

Graphs cap at 25 nodes and 100 edges, with depth and truncation disclosure.
Index completeness refers to the selected file; this is not a repository-wide
flow analysis. Older snapshots still require re-import to acquire call indexes.
All paths are immutable snapshot lookups, workspace isolation remains enforced,
and flow missions skip automatic personal-memory extraction. No code is executed.

The full general-language “Trace login flow” acceptance criterion remains open:
this feature requires an explicit entry function and does not claim verified
cross-file bindings or runtime behavior.

Verification for this feature: 172 backend tests and 66 Flutter tests passed,
along with backend lint/formatting/strict typing and Flutter analysis/formatting.
Coverage includes branches, cycles, ambiguous names, depth/node/edge limits,
legacy indexes, workspace isolation, upload-to-mission flow, personal-memory
exclusion, and graph-to-source navigation. Real-model, live PostgreSQL, browser
visual QA, and native-device acceptance were not rerun.
The release web build also passed with the existing CupertinoIcons font warning.

### Earlier slices

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
