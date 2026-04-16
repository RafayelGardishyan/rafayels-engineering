---
name: re:memory-review
description: Audit the memory layer case bank — view stats, prune stale cases, inspect patterns, and trigger auto-PR generation for learned patterns.
argument-hint: "[optional: stats | stale | prune | patterns]"
---

# Memory Layer Audit & Review

Interactive audit of the rafayels-engineering memory layer. Inspect the case bank,
prune low-value cases, and review detected patterns for possible skill updates.

## Prerequisites

The memory layer must be initialized. If you haven't run `memory init`, do that first:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory init
```

## Execution Flow

### Step 1: Health Check

Start with a doctor check to verify the memory layer is healthy:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory doctor --json
```

If `status` is `unavailable`, stop here and tell the user to install dependencies per the reported `fix` hints.

### Step 2: Show Statistics

```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory report --stats
```

Display the output to the user. Key things to highlight:
- Total cases and status distribution
- Reward distribution (bucket histogram)
- Signal counts by type

### Step 3: Surface Stale Cases

```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory report --stale --older-than 90 --json
```

If there are stale cases, ask the user via AskUserQuestion whether to prune:
- **Prune (dry-run)** — show what would be archived
- **Prune (confirm)** — actually archive low-value stale cases
- **Skip** — leave them

For confirmed prune:
```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory prune --confirm --reward-below 0.3 --older-than 90
```

### Step 4: Inspect Detected Patterns

Check for existing patterns and detect new ones:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/memory-proposer/scripts/memory_proposer.py list --json
python3 ${CLAUDE_PLUGIN_ROOT}/skills/memory-proposer/scripts/memory_proposer.py detect --json
```

For each detected cluster that isn't yet proposed, ask the user whether to:
- **Propose as PR** — generate a draft PR against a target skill
- **Ignore** — mark the pattern as ignored (won't be re-proposed)
- **Skip for now** — leave it as detected

For "Propose as PR", ask which skill to target (e.g. `github`, `compound-docs`, etc.):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/memory-proposer/scripts/memory_proposer.py \
  propose <pattern_id> --target-skill <skill_name>
```

Display the generated PR URL.

### Step 5: Manual Case Management (optional)

If the user wants to inspect a specific case:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory read <case_id> --json
```

To promote an important case (pin it so it's never auto-archived):

```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory promote <case_id>
```

To hard-delete a bad case:

```bash
# First get the confirmation token
TOKEN=$(python3 -c "import hashlib; print(hashlib.sha256(b'delete:<case_id>').hexdigest()[:8])")
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory delete <case_id> --confirm-token $TOKEN
```

## Summary

Present a summary at the end:

```
Memory Review Complete

Stats: <total> cases, <active> active, <promoted> promoted, <quarantine> quarantine
Pruned: <count> cases archived
Patterns: <detected> detected, <proposed> proposed as PRs
PRs created: <list of URLs>
```

## Notes

- **Never auto-merges PRs** — all pattern PRs are created as drafts.
- **Never touches agents/** — memory-proposer refuses to edit files under `agents/`.
- **All destructive operations are dry-run by default** — prune, delete, etc.
