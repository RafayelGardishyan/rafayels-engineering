---
name: dev-log
description: Create or update today's dev log entry in the Obsidian vault. Use after merging a PR or completing significant work.
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash(ls *), Bash(mkdir *), mcp__playwright__browser_take_screenshot, browser_take_screenshot
argument-hint: [optional PR number or feature name]
---

# Dev Log

## Quick Start

Resolve the dev-log directory from project-config, then create or update
today's entry inside it:

```bash
VAULT=$(${CLAUDE_PLUGIN_ROOT}/skills/project-config/scripts/project-config get vault.path)
SUBPATH=$(${CLAUDE_PLUGIN_ROOT}/skills/project-config/scripts/project-config get dev_log.subpath)
DEV_LOG_DIR="${VAULT}/${SUBPATH}"
# Today's entry lives at: ${DEV_LOG_DIR}/YYYY-MM-DD.md
```

Use today's date. Append if the file exists, create if it doesn't.

## Template

```markdown
# Dev Log — YYYY-MM-DD

## [PR Title or Feature Name]

**PR:** #NNN (if applicable)
**Branch:** branch-name

### What changed
- [Bullet point summary of changes]

### Key decisions
- [Any architectural or design decisions made]

### Screenshots
![[assets/filename.png]]
```

## Screenshots

If UI changes were made:

1. Take screenshots using the available browser tooling
   - Pi: `browser_take_screenshot`
   - Claude/OpenCode: Playwright MCP or equivalent browser tooling
2. Save to the `assets/` subfolder inside `${DEV_LOG_DIR}` (resolved above)
3. Embed in the dev log with `![[assets/filename.png]]`
