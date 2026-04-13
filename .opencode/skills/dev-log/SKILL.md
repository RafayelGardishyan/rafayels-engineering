---
name: dev-log
description: Create or update today's dev log entry in the Obsidian vault. Use after merging a PR or completing significant work.
argument-hint: [optional PR number or feature name]
---

# Dev Log

## Quick Start

Create or update today's entry at:

```
/Users/rgardishyan/Documents/vault/Parai/Parai/Documentatie/parai-core/Dev Log/YYYY-MM-DD.md
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

1. Take screenshots using the Playwright MCP
2. Save to: `/Users/rgardishyan/Documents/vault/Parai/Parai/Documentatie/parai-core/Dev Log/assets/`
3. Embed in the dev log with `![[assets/filename.png]]`
