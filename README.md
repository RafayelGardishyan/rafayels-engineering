# rafayels-engineering

Rafayel's engineering toolkit for **Claude Code**, **OpenCode**, and now **Pi**.

This repo stays compatible with the existing Claude/OpenCode plugin layout while also shipping a native **Pi package** with extensions for the tools that matter most:

- memory
- project-config
- browser / Playwright-style automation
- Figma access

## Compatibility

| Harness | Status | Entry point |
|---|---|---|
| Claude Code | Supported | `.claude-plugin/plugin.json` |
| OpenCode | Supported | `.opencode/` |
| Pi | Supported | `package.json` + `extensions/` |

## What changed for Pi

This repository now includes a Pi package manifest and native Pi extensions under `extensions/`.

### Native Pi extensions

- `extensions/memory.ts`
- `extensions/project-config.ts`
- `extensions/playwright.ts`
- `extensions/figma.ts`
- `extensions/ask-user-question.ts`
- `extensions/issue-tracker.ts`
- `extensions/toon.ts` (global Toon preprocessor for tool output)

These extensions are additive. They do **not** replace the existing Claude/OpenCode plugin files.

### New workflow primitives

This package now also includes two Pi-native workflow tools:

- `ask_user_question` — interactive single-question user input for workflow pauses and clarifications
- `issue_tracker` — project-local structured issue tracking backed by JSON files in `.pi/issues/`

## Installation

Use the installer:

```bash
./install.sh
```

The installer lets you choose:
- target agent: Pi / Claude Code / OpenCode / all
- project-local vs global where relevant

See also: [INSTALL.md](./INSTALL.md)

## Pi usage

Install globally:

```bash
pi install /path/to/rafayels-engineering
```

Install into the current project only:

```bash
pi install -l /path/to/rafayels-engineering
```

## Toon preprocessing (Pi)

`extensions/toon.ts` now runs a **transparent Pi-native preprocessing pipeline** for Bash tools:

1. It tries to rewrite each command through `rtk rewrite` first (when available).
2. It always applies Toon-style JSON compression to tool output in Pi when available.

This is enabled by default and works without special env toggles.

Modes are mainly for control/rollback:

```bash
export PI_TOOL_PREPROCESSOR=auto   # (default) rewrite with RTK when possible, then encode output with Toon
export PI_TOOL_PREPROCESSOR=rtk    # force RTK rewrite attempt first, then Toon encoding
export PI_TOOL_PREPROCESSOR=toon   # skip RTK, only do Toon output encoding
export PI_TOOL_PREPROCESSOR=off    # disable preprocessing entirely

# Optional binary/script overrides
export TOON_BIN=/opt/homebrew/bin/toon
export RTK_BIN=/opt/homebrew/bin/rtk
export TOON_DETECT_SCRIPT=/path/to/custom/toon-detect.sh
```

## Memory setup

Initialize memory once:

```bash
python3 skills/memory/scripts/memory.py init
```

If your machine needs a specific interpreter:

```bash
export PYTHON_FOR_RAFAYELS_ENGINEERING=/opt/homebrew/bin/python3.12
```

## Migration notes

### Claude / OpenCode users

Nothing is removed:
- existing plugin manifests remain
- codex-related files remain
- MCP-based Claude flows remain available

### Pi users

Pi uses native extensions instead of relying on Claude MCP wiring.

Examples:
- memory becomes Pi tools like `memory_query` and `memory_write`
- project config becomes Pi tools like `get_config_value` and `init_config`
- browser automation is exposed as Pi tools and also compatibility aliases for existing prompt content
- Figma is exposed through native HTTP-based Pi tools

## Browser compatibility layer

To reduce prompt churn, the Pi Playwright bridge also registers compatibility aliases matching existing prompt usage, such as:

- `mcp__plugin_compound-engineering_pw__browser_navigate`
- `mcp__plugin_compound-engineering_pw__browser_snapshot`
- `mcp__plugin_compound-engineering_pw__browser_take_screenshot`
- `mcp__plugin_compound-engineering_pw__browser_console_messages`

That means existing command text can keep working while the underlying execution is Pi-native.

## Figma support

Pi-native Figma tools currently include:
- `figma_get_node`
- `figma_get_node_from_url`
- `figma_get_file`
- `figma_get_image`

Requires:

```bash
export FIGMA_API_KEY=...
```

## Project config support

Pi-native project-config tools currently include:
- `get_config_value`
- `get_all_config`
- `get_config_source`
- `list_config_keys`
- `init_config`

These wrap the existing Python resolver/CLI so behavior stays aligned across harnesses.

## Repository structure

- `.claude-plugin/` — Claude Code plugin manifest
- `.opencode/` — OpenCode config and resources
- `extensions/` — Pi-native extensions
- `skills/` — shared skills
- `commands/` — prompt/command content
- `mcp-servers/` — Claude/OpenCode MCP servers that remain supported

## Current direction

This repo is now **multi-harness**:
- preserve Claude/OpenCode compatibility
- add Pi-native support where it improves installability and runtime behavior
- especially move important operational tooling like memory into first-class Pi tooling
