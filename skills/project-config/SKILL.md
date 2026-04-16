---
name: project-config
description: Resolves project-scoped configuration (vault path, ADR project, memory DB, dev-log subpath, docs dirs) from layered .rafayels/ YAML files + env vars. Used by every skill that touches user paths.
disable-model-invocation: true
allowed-tools: Bash, Read, Write
---

# Project Config

Use this skill when a script or skill needs the project's resolved vault path,
ADR project slug, memory DB path, dev-log subpath, or docs directories.

## Usage

```bash
${CLAUDE_PLUGIN_ROOT}/skills/project-config/scripts/project-config get vault.path
```

```bash
${CLAUDE_PLUGIN_ROOT}/skills/project-config/scripts/project-config list --json
```

Config resolution precedence is:

1. `RAFAYELS_*` environment variables
2. `.rafayels/config.local.yaml`
3. `.rafayels/config.yaml`

Use `.rafayels/config.yaml` for team defaults and
`.rafayels/config.local.yaml` for personal overrides.
