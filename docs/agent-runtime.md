# Agent runtime

Phase 1 implements a bounded, provider-neutral agent loop in
`services/nexus_server/app/agent`. The runtime owns orchestration; model
providers can propose typed data but cannot execute tools directly.

## Lifecycle

```text
created -> planning -> executing -> observing -> completed
                         |             |
                         |             +-> executing
                         +-> waiting_for_approval
                         +-> replanning -> executing

Any active state may fail through a structured runtime error.
```

Each transition is checked by `AgentStateMachine`. Terminal runs are not
executed again, and runs waiting for approval pause before their tool call.
Approval continuation, rejection/replanning, and cancellation have REST
endpoints. Execution and actions are serialized per run within one server
process. Cancelling an active run interrupts its task; replaying an old snapshot
reloads the stored state before any work can run again.

## Loop contract

1. The planner requests a `Plan` with one to twelve schema-validated steps.
2. The executor requests an `ExecutionDecision` for the current step.
3. A named tool is resolved only through `ToolRegistry`.
4. Validated output becomes an observation in the run context.
5. The runtime advances, replans, responds, pauses, or fails.

Every iteration and meaningful transition appends a monotonically ordered trace
entry. `NEXUS_MAX_AGENT_ITERATIONS` prevents unbounded execution. Provider,
planning, tool, permission, timeout, and iteration failures become structured
`RunError` values rather than uncaught API exceptions.

## Provider boundary

The `LLMProvider` interface accepts messages, optional tool definitions, and an
optional response schema. Implementations currently include:

- `ollama` for local/self-hosted inference;
- `openai_compatible` for configurable compatible HTTP endpoints;
- `mock` for deterministic tests, CI, and local demonstrations.

Provider credentials remain in backend settings. Logs and API errors never
include secret values or raw provider response bodies.

## API and storage

- `POST /api/v1/runs` returns a created snapshot and schedules bounded execution.
- `GET /api/v1/runs` lists runs for a user.
- `GET /api/v1/runs/{run_id}` returns the typed run and ordered trace.

Runs, ordered events, tasks, and artifacts use PostgreSQL outside tests.
Tests use repository interfaces with memory stores and separate SQL persistence
coverage. Events replay at `/ws/runs/{run_id}?last_seen_sequence=N` or through
`GET /api/v1/runs/{run_id}/events?after=N`.

The client restores the snapshot and trace before subscribing after its final
sequence. Completed runs need no socket. Duplicate events and stale responses
from previously selected runs cannot alter current progress.

Task creation and event writes are separate transactions. This release does
not provide crash-safe exactly-once execution or distributed workers. An abrupt
process exit can leave an unfinished run requiring operator attention. See
[missions](missions.md) for scope and verification.
