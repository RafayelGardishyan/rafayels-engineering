---
name: project-config
description: Resolves project-scoped configuration (vault path, ADR project, memory DB, dev-log subpath, docs dirs) from layered .rafayels/ YAML files + env vars. Used by every skill that touches user paths.
disable-model-invocation: true
allowed-tools: Bash, Read, Write
---

# Project Config

Use this skill when a script or skill needs the project's resolved vault path,
ADR project slug, memory DB path, dev-log subpath, or docs directories.

## First-run bootstrap

```bash
${CLAUDE_PLUGIN_ROOT}/skills/project-config/scripts/project-config init
```

Interactively prompts for `vault.path`, `adr.project`, `dev_log.subpath`, and
writes `.rafayels/config.yaml` (chmod 0600). Adds `.rafayels/config.local.yaml`
to the project `.gitignore` so personal overrides stay out of git.

Non-interactive variant for agents:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/project-config/scripts/project-config init \
  --non-interactive \
  --set vault.path=~/Documents/vault \
  --set adr.project=my-project \
  --set dev_log.subpath="Docs/Dev Log"
```

## Reading config

```bash
${CLAUDE_PLUGIN_ROOT}/skills/project-config/scripts/project-config get vault.path
${CLAUDE_PLUGIN_ROOT}/skills/project-config/scripts/project-config list --json
${CLAUDE_PLUGIN_ROOT}/skills/project-config/scripts/project-config check
```

Exit codes: `0` success, `1` unknown key, `2` missing required key, `3` malformed.

Agents can call the equivalent MCP tools instead: `get_config_value`,
`get_all_config`, `get_config_source`, `list_config_keys`, `get_project_root`,
`check_config`, `init_config`.

## Resolution precedence

1. `RAFAYELS_*` environment variables (e.g. `RAFAYELS_VAULT_PATH`)
2. `.rafayels/config.local.yaml` — personal overrides (gitignored)
3. `.rafayels/config.yaml` — team defaults (committed)
4. Schema defaults

## Schema

| Key | Required | Default |
|---|---|---|
| `schema_version` | yes | `1` |
| `vault.path` | yes | — |
| `adr.project` | yes | — |
| `dev_log.subpath` | yes | — |
| `memory.db_path` | no | `~/.claude/plugins/rafayels-engineering/memory.db` |
| `docs.brainstorms_dir` | no | `docs/brainstorms` |
| `docs.plans_dir` | no | `docs/plans` |
