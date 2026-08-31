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
Approval continuation and cancellation endpoints arrive with the streaming UI
phase.

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

- `POST /api/v1/runs` creates and executes a bounded run.
- `GET /api/v1/runs` lists runs for a user.
- `GET /api/v1/runs/{run_id}` returns the typed run and ordered trace.

Phase 1 repositories are process-local and intentionally hidden behind
interfaces. PostgreSQL persistence and resumable event delivery are later
phases; restarting the API currently clears runs and tasks.
