# Mission system (Phase 5)

A goal can create a multi-step plan, execute registered tools, and leave durable
tasks and artifacts. The dashboard shows active and historical runs. Opening a
saved run restores its timeline without restarting execution.

## API

| Operation | Endpoint |
| --- | --- |
| Start/list/get runs | `POST /api/v1/runs`, `GET /api/v1/runs`, `GET /api/v1/runs/{id}` |
| List tasks, optionally per mission | `GET /api/v1/tasks?run_id=...` |
| Complete/reopen a task | `PATCH /api/v1/tasks/{id}` with `{"status":"completed"}` or `pending` |
| List artifacts, optionally per mission | `GET /api/v1/artifacts?run_id=...` |
| Read one artifact | `GET /api/v1/artifacts/{id}` |

Task and artifact APIs default to the `local` workspace; `user_id` selects a
workspace. This is not authentication. These routes are for trusted local use.

The `create_artifact` tool accepts `type`, `title`, and `content`. Ownership and
run linkage come from the runtime context, never model arguments. Supported
types are plan, checklist, note, report, study_guide, architecture_diagram, and
code_explanation. Flutter renders checklists as rows and code/diagram source in
monospace; prose is selectable text. Diagram source is not executed or rendered
as executable HTML.

## Storage and execution

Production/development resources select SQL task and artifact repositories.
Test resources select isolated memory repositories. Both enforce workspace
scoping on task changes and artifact reads. SQL tests also reopen a file-backed
database and confirm task completion and artifact content survive disposal.

The runtime serializes actions and execution per run in one process. It reloads
stored state before executing a supplied snapshot and interrupts active work on
cancellation. Rejection records the denied action in replanning context and
consumes an iteration; it does not run that step immediately.

The client loads historical snapshots before subscribing after their last
sequence. Duplicate and unrelated events are ignored, and a late response from
an old selection cannot replace the current mission.

## Verification

- Backend: 42 tests passed, including two-step task/artifact execution, owner
  isolation, invalid task status, SQL reopen, cancellation, and duplicate execution.
- Flutter: 13 tests passed, including historical loading, reconnect cursor,
  stale-response protection, task toggle, artifact expansion, and approval UI.
- Strict backend typing and client analysis pass.
- Flutter release web build succeeds. Browser visual QA and real-device testing
  have not been performed for this milestone.
- Docker: mock goal `Create a Flutter architecture study guide` completed two
  steps, emitted 23 ordered events, created one task and one study guide.
- After an API container restart, the run, completed task status, artifact
  content, and replay events 8 through 23 remained available from PostgreSQL.
  WebSocket replay also returned all 16 events after cursor 7.

To repeat the read-only smoke check after running the mock study-guide demo:

```powershell
.\.venv\Scripts\python.exe scripts/mission_smoke.py <run_id> --user-id local
```

This check expects the two-step mock demo, one task, and one study-guide artifact;
it is not a general validator for arbitrary missions.

## Main changed files

- Backend: `app/storage/{tables,task_repository,artifact_repository,resources}.py`
- API/tool: `app/api/routes/{tasks,artifacts}.py`, `app/tools/create_artifact.py`
- Runtime/demo: `app/agent/runtime.py`, `app/providers/mock.py`
- Flutter: `lib/features/missions/{application,data,domain,presentation}/`
- Outputs: `lib/features/outputs/{data/outputs_api,presentation/outputs_screen}.dart`
- Routing: `lib/routing/app_router.dart`
- Tests: `test_mission_outputs.py`, `test_output_persistence.py`,
  `test_agent_runtime.py`, `mission_controller_test.dart`,
  `missions_screen_test.dart`, `outputs_screen_test.dart`

The associated commits contain the full changed-file lists.

## Remaining work

Voice, code intelligence, scheduling, notifications, distributed execution,
and automatic crash recovery remain outside this milestone. Existing document
and memory features still need broader integration coverage, memory retrieval
in planning, editing controls, and citation presentation. Their presence in the
handoff should not be read as proof that every earlier-phase acceptance
criterion has been verified. Real model inference was not exercised in this
mock-provider verification.

The fallback document embedding now uses SHA-256 for stability across processes.
Documents indexed with the older process-randomized fallback should be reindexed.
Optional sentence-transformer models must already be cached locally; startup
does not download them automatically.
