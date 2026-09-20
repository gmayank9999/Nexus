# Saved-memory retrieval

The agent tool registry now exposes the read-only `search_memories` tool. The
planner can select it when a goal needs saved preferences, facts, or project
context. Retrieval runs through normal tool validation, permission checks,
timeouts, observations, and timeline events. It does not silently preload
memories into every new mission.

## Try the deterministic demo

Create a memory through `POST /api/v1/memories`, for example:

```json
{"category":"user_preference","content":"Prefers Flutter examples"}
```

With the mock LLM provider, start a mission from Home with:

```text
Search memories for Flutter
```

The mock recognizes this explicit prefix and performs a real repository search.
The final reply lists matching saved excerpts and their memory IDs, labeled as
unverified facts. Open mission details and expand the tool-completed event to
inspect confidence, source, category, originating run, and update time. No task
is created by this demo. Edit or forget a memory and run the query again to see
the current store; existing historical run traces remain unchanged.

The mock is not a general reasoning model. Real-model tool selection and response
quality require separate evaluation with an explicitly configured provider.

## Search contract

- Required query: 1–200 characters containing words or numbers.
- Optional category and minimum confidence (default 0.6).
- Optional result limit: 1–5, default 5.
- Search scope: at most the 100 most recently updated qualifying memories from
  `ToolContext.user_id`; arguments cannot override the workspace.
- Matching: Unicode case-folded word overlap against the first 500 characters
  of each memory. No embeddings, stemming, synonym expansion, or external service.
- Ranking: overlap, confidence, update recency, then ID for stable ties.
- Output: at most 2,500 content characters, plus provenance metadata. Flags
  disclose shortened content, additional matches, and reaching the candidate cap.

This is a bounded recent-memory search, not an exhaustive search over the full
store. No results do not prove there are no relevant memories. Full-text indexing
and relevance evaluation remain future work.

## Privacy and safety

Only the current workspace is read. Workspace labels are not authentication;
NEXUS still requires trusted local deployment. Retrieval does not alter memory,
approve actions, or execute text stored inside a memory. Prompt guidance treats
results as untrusted context; it is not a complete prompt-injection defense.
Registered-tool constraints and permission checks remain in force.

Retrieved excerpts are persisted in the mission's observations and events. They
may be sent to the configured LLM provider in later execution/replanning steps,
and can appear in bounded follow-up context. Forgetting a source memory prevents
future searches from returning it but does not erase earlier mission snapshots.

## Verification

104 backend tests passed, including ranking, workspace isolation, category and
confidence filters, Unicode matching, query validation, result/candidate/content
budgets, live edits/deletions, and a mock mission API-to-tool-to-timeline flow.
Backend lint and strict typing passed. No frontend code changed in this slice;
browser, real-model, and PostgreSQL runtime verification were not rerun.

This adds planner-selectable retrieval, not automatic relevant-memory injection.
Extraction policy, semantic search, real-model acceptance, and broader Phase 4
integration remain open. See [memory controls](memory-controls.md) for editing
and legacy-workspace behavior.
