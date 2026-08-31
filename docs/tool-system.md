# Tool system

Tools are explicit backend capabilities, not arbitrary model-generated code.
Every tool declares a stable name, description, Pydantic input model,
permission level, timeout, and async implementation.

## Execution boundary

`ToolRegistry` is the only supported execution path. It:

1. rejects unregistered names;
2. checks the permission policy;
3. validates arguments against the tool input schema;
4. enforces a per-tool timeout;
5. normalizes output and duration into a `ToolResult`.

The initial safe registry contains:

| Tool | Permission | Purpose |
| --- | --- | --- |
| `calculator` | read-only | Evaluates a restricted arithmetic AST |
| `current_time` | read-only | Returns time for a validated IANA timezone |
| `create_task` | local write | Creates a user-scoped task record |
| `list_tasks` | read-only | Lists task records for the current user |

The calculator accepts only numeric constants and whitelisted arithmetic
operators. It never calls `eval`. Task tools receive the authenticated user
identity through `ToolContext`; the model cannot choose another user.

## Permission policy

- Read-only and local-write tools may run automatically.
- External actions require approval.
- Dangerous tools are denied even when an approval flag is supplied.

Shell execution, arbitrary Python, raw SQL, file deletion, unrestricted HTTP,
browser control, and computer control are not registered. Adding a capability
requires a concrete tool class, a narrow schema, a permission classification,
tests, and explicit registration in application resources.
