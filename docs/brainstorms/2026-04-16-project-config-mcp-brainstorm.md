---
date: 2026-04-16
topic: project-config-mcp
---

# project-config MCP Server

## What We're Building

A new `project-config` MCP server (plus a matching `project-config` CLI, both
backed by a single Python resolver module) that replaces the hardcoded paths
currently scattered across `rafayels-engineering` plugin skills. Values are
read from a committed `.rafayels/config.yaml` (team defaults) overlaid with a
gitignored `.rafayels/config.local.yaml` (per-user) and optional environment
variable overrides.

The motivation: multiple teammates now use the same projects, but today's
plugin bakes the author's personal paths into skill markdown and Python
scripts (vault dir, ADR project name, even the absolute Dev Log path). As
soon as someone else clones a repo, those paths fail. The project-config
server becomes the single source of truth every skill, command, or script
consults when it needs a project-scoped path.

## Why This Approach

Three shapes were considered. **Minimal surface** (vault + ADR + dev_log only)
was tempting by YAGNI, but it leaves the next few obvious config needs
(memory DB override, doc directories, default model) as a predictable stream
of follow-up PRs. **Schema-less passthrough** was rejected — no validation,
no `init` wizard seed values, typos silently return misses. **Rich config
surface** was chosen: broader schema now, so the `init` wizard has a real
template to offer, the resolver validates known keys, and future callers
don't each reinvent key names.

The MCP-only and CLI-only options were also rejected. MCP-only leaves Python
scripts (`memory.py`, future helpers) without a callable surface; CLI-only
abandons the agent tool interface the user originally asked for. The agreed
shape is a shared Python resolver wrapped by both a FastMCP server (matching
the existing `codex-bridge` pattern at `mcp-servers/codex-bridge/server.py`)
and a small CLI — the two front-ends cannot disagree because they call the
same code.

## Key Decisions

- **Config location:** `.rafayels/config.yaml` (committed) + `.rafayels/config.local.yaml` (gitignored). Rationale: keeps team defaults reviewable in PRs while letting each teammate override locally without polluting git history.
- **Precedence (low → high):** team file → local file → `RAFAYELS_*` env vars. Rationale: env wins so CI and one-off overrides always work.
- **Resolver architecture:** one Python module consumed by both an MCP server and a CLI. Rationale: prevents drift between agent tool calls and shell-script calls.
- **Missing config behavior:** loud failure with actionable message, plus a `project-config init` wizard. Rationale: silent fallback hides bugs and points at the wrong vault; `init` keeps first-run friction low.
- **Memory DB stays shared:** `memory.db_path` is a config key, but defaults to today's `~/.claude/plugins/rafayels-engineering/memory.db`. Rationale: cross-project learning is a current feature; isolation is opt-in, not forced.
- **Migration:** all hardcoded consumers rewritten in this PR (`skills/dev-log/SKILL.md`, `skills/using-adr-plugin/SKILL.md`, and any other literal paths surfaced during implementation). The PR also adds `.rafayels/config.local.yaml` to `.gitignore`. Rationale: no two-sources-of-truth window, no accidental check-in of per-user overrides.
- **Config schema (v1):** `vault.path`, `adr.project`, `dev_log.subpath`, `memory.db_path`, `docs.brainstorms_dir`, `docs.plans_dir`. Rationale: every key maps to a path that is either already hardcoded somewhere or obvious next-up (doc dirs). `default_model` was considered and dropped — no current consumer.

## Open Questions

- Exact YAML schema shape — flat keys vs nested objects — deferred to plan phase.
- Where to register the MCP server in `.claude-plugin/plugin.json` and what stdio command to use — template exists in codex-bridge, details in plan.
- How the resolver handles path expansion (`~`, env vars inside values) — should be explicit in plan.
- Whether `project-config init` should probe the environment (e.g. suggest vault paths from likely locations) or stay purely prompt-driven — plan decides.
- Whether the `.rafayels/` directory needs a README or example file checked in for discoverability.

## Next Steps

→ `/workflows:plan` for implementation details
