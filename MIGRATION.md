# Harness Migration / Compatibility Guide

This repo is no longer Claude-only.

It now supports three execution models at the same time:

1. **Claude Code plugin** via `.claude-plugin/plugin.json`
2. **OpenCode project resources** via `.opencode/`
3. **Pi package + native extensions** via `package.json` and `extensions/`

## Goal

Add Pi support **without breaking** the existing Claude/OpenCode plugin behavior.

## What stays as-is

- `.claude-plugin/plugin.json`
- existing MCP servers used by Claude/OpenCode
- `.opencode/` resources
- codex files remain in the repo even if they are not ported to Pi right now

## What is native in Pi now

### Memory
- `memory_write`
- `memory_query`
- `memory_signal`

### Project config
- `get_config_value`
- `get_all_config`
- `get_config_source`
- `list_config_keys`
- `init_config`

### Browser automation
- `browser_navigate`
- `browser_snapshot`
- `browser_take_screenshot`
- `browser_console_messages`
- `browser_click`
- `browser_type`
- `browser_fill`

Plus compatibility aliases for existing prompt text:
- `mcp__plugin_compound-engineering_pw__browser_navigate`
- `mcp__plugin_compound-engineering_pw__browser_snapshot`
- `mcp__plugin_compound-engineering_pw__browser_take_screenshot`
- `mcp__plugin_compound-engineering_pw__browser_console_messages`

### Figma
- `figma_get_node`
- `figma_get_node_from_url`
- `figma_get_file`
- `figma_get_image`

## Important implementation note

Where possible, Pi extensions wrap the **existing project CLIs/scripts** instead of rewriting logic from scratch. This keeps behavior aligned across harnesses.

Examples:
- memory Pi tools wrap `skills/memory/scripts/memory.py`
- project-config Pi tools wrap `skills/project-config/scripts/cli.py`

## Environment variables

### Python override

```bash
export PYTHON_FOR_RAFAYELS_ENGINEERING=/opt/homebrew/bin/python3.12
```

### Figma

```bash
export FIGMA_API_KEY=...
```

## Recommended rollout path

1. Keep Claude/OpenCode flows working unchanged.
2. Add Pi-native tools where MCP dependence hurts UX or installability.
3. Update prompts/skills gradually to mention harness-native alternatives.
4. Preserve compatibility aliases where prompt churn would be expensive.
