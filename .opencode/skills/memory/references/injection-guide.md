# Workflow Integration Guide

How workflow markdown files hook into the memory layer.

## Push vs Pull

The memory layer supports **both** injection models:

### Push: deterministic phase-boundary injection

Workflow files call `memory query` at phase boundaries. The retrieved cases
are injected into the phase context as markdown. Predictable token cost,
runs every time.

### Pull: agent-initiated mid-phase lookup

Agents running inside a workflow phase can call `memory query` themselves
when a problem or decision point arises. Emergent capability — agents explore
the case bank as questions emerge.

Both paths share the same retrievals log so cross-phase dedup and cap
penalty logic apply uniformly.

## Standard Hook Pattern

At the start of a phase:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory query \
  "<query text>" --phase <phase_name> --k 3 --format md 2>/dev/null
```

- If stdout is non-empty, include it in phase context.
- Exit code 75 = memory unavailable. Proceed without injection.
- Empty output = cold-start threshold not met (fewer than K*3 active cases).
  Proceed without injection.

At the end of a phase (capture):

```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory write \
  --phase <phase_name> \
  --query "<feature description>" \
  --title "<short title>" \
  --plan "<approach>" \
  --outcome "<result>" \
  --tags '["tag1","tag2"]' \
  --json
```

Capture the returned `case_id` for signal emission.

At event moments (signals):

```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory signal \
  <case_id> <type> <value> --source "<source>"
```

## Cross-Phase Dedup

Within a single `/re:feature` run, pass `--exclude <ids>` and `--run-id <uuid>`
to prevent the same case showing up in multiple phases:

```bash
# Phase 1 query
memory query "..." --phase brainstorm --k 3 --run-id $RUN_ID
# Save the returned case_ids

# Phase 2 query — exclude what we've already seen
memory query "..." --phase plan --k 3 --run-id $RUN_ID --exclude 1,2,3
```

## Exit Codes for Workflow Hooks

| Code | Workflow behavior |
|---|---|
| 0 | Success — use output |
| 1 | Not found (e.g. `read <id>` missing) — continue |
| 2 | Validation error (bad args) — log and continue |
| 3 | Storage error — log and continue |
| 75 | Memory unavailable (deps missing) — continue silently |

Never treat any non-zero as fatal in workflow hooks. Memory is opt-in.
