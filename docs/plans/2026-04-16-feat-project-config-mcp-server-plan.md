---
date: 2026-04-16
type: feat
topic: project-config-mcp-server
brainstorm: docs/brainstorms/2026-04-16-project-config-mcp-brainstorm.md
status: draft
deepened: 2026-04-16
---

# ✨ feat: project-config MCP server + CLI + shared resolver

## Enhancement Summary (Deepen Findings)

**Deepened on:** 2026-04-16 via 8 parallel agents (framework docs, best practices, architecture, simplicity, security, Python review, agent-native, pattern conformance).

### Key Updates Integrated

1. **Security hardening** — explicit `yaml.safe_load`, custom `UniqueKeyLoader` rejecting duplicate keys, 64KB file-size cap, per-key path allowlist to block `../../../` traversal, `chmod 0600` on local config writes, "don't store secrets" YAML header comment.
2. **FastMCP idioms** — sync tools (no async wrapping for pure file reads), `mcp.run(transport="stdio")` explicit form, pin `mcp>=1.26,<2.0`, stderr-only logging (stdout is the protocol channel), minimal server skeleton provided below.
3. **Agent-native parity gaps closed** — added `list_config_keys()` MCP tool + `project-config keys` CLI (schema discoverability), `get_project_root()` MCP tool, `get_config_source(key)` MCP tool, `project-config init --non-interactive --set key=value` for agent-driven bootstrapping.
4. **Python hardening** — `yaml.safe_load` + `UniqueKeyLoader`, `@functools.lru_cache(maxsize=1)` on `load_config`, `MappingProxyType` for `source_map` immutability, `slots=True` on the `ProjectConfig` dataclass, `from __future__ import annotations` headers, iterate over the known schema when building env overlay (not `os.environ`).
5. **Simplification per YAGNI review** — drop `strict=True` + `ConfigPathNotFoundError`, drop `project-config where` and `project-config path` CLI commands, drop init wizard probing in favor of plain prompt-with-default, collapse `UnknownConfigKeyError` into `ConfigMissingError` with a `reason` attribute. Test list trimmed from 13 to 8 high-value cases.
6. **Import cleanliness** — add `pyproject.toml` + pytest `pythonpath` to replace `sys.path` hacks in tests; production consumers still use a single isolated `_import_resolver()` helper so the path logic lives in one place.
7. **Pattern conformance** — SKILL.md gets explicit frontmatter (`name`, `description`, `disable-model-invocation: true`, `allowed-tools`), all bash examples prefixed with `${CLAUDE_PLUGIN_ROOT}/...`, wrapper script drops the memory-layer's interpreter-probing logic (not needed — project-config has no sqlite-vec dependency).
8. **Schema versioning** — add top-level `schema_version: 1` to YAML now (cheap; unlocks future migration). Answers an open question.

### Critical Findings Surfaced
- **Architecture**: resolver import from `mcp-servers/` → `skills/` inverts directory-implied dependencies. Mitigated by single `_import_resolver()` helper and `pyproject.toml`; full move to `lib/` deferred.
- **Security**: YAML parsing + path expansion without an allowlist is a real traversal vector. Now required.
- **Agent-native**: MCP previously had 3 tools vs CLI's 6; closed most gaps.

### Sources
- Anthropic MCP Python SDK v1.26 source (confirmed sync-tool dispatch, stderr rules).
- pyyaml issues #235 (billion-laughs), #165 (duplicate keys).
- pydantic-settings, dynaconf, environs, typed-settings comparison.
- Codebase precedent: `mcp-servers/codex-bridge/server.py`, `skills/memory/scripts/db.py`, `skills/memory/scripts/memory` wrapper.

---

# ✨ feat: project-config MCP server + CLI + shared resolver

Replace every hardcoded path in the `rafayels-engineering` plugin (vault
location, ADR project name, memory DB, dev-log subpath, docs directories)
with a single source of truth served by a new `project-config` MCP server
and an equivalent `project-config` CLI. Both front-ends wrap one Python
resolver module, so agent tool calls and shell-script calls cannot
disagree.

## Motivation

The plugin currently ships with the author's personal paths baked into
skill markdown, Python scripts, and shell hooks. As soon as a second
teammate clones a repo, those paths fail — they point at a non-existent
vault, an ADR project only the author has, or an absolute dev-log path
tied to `/Users/rgardishyan/`. The brainstorm surfaced 14 hardcoded
`parai-core` mentions in `skills/using-adr-plugin/SKILL.md` alone, plus
two literal memory-DB paths and a hardcoded vault prefix
(`~/Documents/vault/Parai/Parai/Documentatie/parai-core/`).

Fixing this per-skill with one-off env vars would spread the pattern
thinly across the codebase and leave no affordance for future config
needs (per-project memory DB, per-user model preference, alternate docs
layouts). A single resolver keeps naming consistent, validates keys, and
gives the first-run wizard a real schema to populate.

## Acceptance Criteria

- [ ] `mcp-servers/project-config/server.py` runs as a FastMCP stdio server (sync tools, `mcp.run(transport="stdio")`, stderr-only logging), registered in `.claude-plugin/plugin.json` alongside `codex-bridge`.
- [ ] `mcp-servers/project-config/requirements.txt` pins `mcp>=1.26,<2.0` + `pyyaml>=6.0`. Same `mcp` pin added to `mcp-servers/codex-bridge/requirements.txt`.
- [ ] `skills/project-config/scripts/project-config` CLI wrapper (plain `exec python3 cli.py "$@"` — no interpreter probing) runs the same resolver and prints results in human or `--json` form.
- [ ] `skills/project-config/scripts/resolver.py` exports `load_config()`, `discover_project_root()`, `lookup()`, `SCHEMA`, and the two exception classes. Uses `@lru_cache(maxsize=1)`; `cache_clear()` available for reload.
- [ ] Layered config (`.rafayels/config.yaml` + `.rafayels/config.local.yaml` + `RAFAYELS_*` env vars) with documented precedence. Env overlay iterates schema keys (not `os.environ`).
- [ ] v1 schema keys: `schema_version`, `vault.path`, `adr.project`, `dev_log.subpath`, `memory.db_path`, `docs.brainstorms_dir`, `docs.plans_dir`.
- [ ] `project-config init` interactive wizard writes `.rafayels/config.yaml` with `chmod 0600`. `--non-interactive --set key=value` supported for agent-driven bootstrap.
- [ ] Missing required keys raise `ConfigMissingError(reason="missing")` with an actionable message; unknown keys raise `ConfigMissingError(reason="unknown")` with a difflib suggestion.
- [ ] **YAML is parsed with `yaml.safe_load` only, via a `UniqueKeyLoader` that rejects duplicate keys. Files >64KB are rejected before parsing.**
- [ ] **Path-typed values are checked against a per-key allowlist after expansion; `..` traversal raises `ConfigMalformedError`.**
- [ ] MCP tools: `get_config_value`, `get_all_config`, `get_config_source`, `list_config_keys`, `get_project_root`, `check_config`, `init_config`. All return `{"status": "ok"|"error", ...}`; never raise past the boundary.
- [ ] CLI subcommands: `get`, `list`, `keys`, `check`, `init` (interactive + `--non-interactive`). `--json` works on every subcommand including error exits.
- [ ] `.rafayels/config.local.yaml` added to `.gitignore`.
- [ ] Every hardcoded consumer migrated in this PR: `skills/memory/scripts/db.py` (with logged fallback), `skills/memory/SKILL.md`, `skills/dev-log/SKILL.md`, `skills/using-adr-plugin/SKILL.md` (14 `parai-core` lines), plus any others surfaced during implementation.
- [x] Unit tests for resolver (10 cases listed in Phase 1) all pass.
- [ ] Integration smoke test: `project-config get vault.path --json` returns the expected resolved path from a test fixture.
- [ ] Existing memory layer tests still pass after migration.

## Context & Research Findings

### Project conventions (from repo-research-analyst)

| Finding | File | Implication |
|---|---|---|
| FastMCP stdio pattern exists | `mcp-servers/codex-bridge/server.py:16-18`, `:230-231` | Copy structure: `FastMCP("project-config")`, `@mcp.tool()` decorators, `mcp.run("stdio")` at bottom. |
| Plugin registration by relative path | `.claude-plugin/plugin.json:26-32` | Add sibling entry with `"command": "python3"` and `"args": ["mcp-servers/project-config/server.py"]`. |
| `@dataclass(frozen=True)` Config precedent | `skills/memory/scripts/db.py:46-73` | Reuse exact pattern: frozen dataclass + `classmethod load()` + `assert_compatible()`. |
| CLI convention is `skills/<name>/scripts/<name>` | `skills/memory/scripts/memory` (wrapper added earlier this session) | New CLI goes at `skills/project-config/scripts/project-config`. Not under `mcp-servers/`. |
| `pyyaml>=6.0` already required | `skills/memory/scripts/requirements.txt` | No new dependency needed for YAML parsing. |
| Test pattern uses sibling-import in `conftest.py` | `skills/memory/scripts/tests/conftest.py` | Mirror for `skills/project-config/scripts/tests/conftest.py`. |
| 14 `parai-core` literals in ADR skill | `skills/using-adr-plugin/SKILL.md` (see grep lines 60-253) | All must become `{{adr.project}}` or be rewritten to read from resolver. |
| `.opencode/` mirror is drifting | `.opencode/skills/*/` | Out of scope: do NOT add `.opencode/` copies for new MCP. Note drift in follow-up. |
| Two memory-DB literals | `skills/memory/scripts/db.py:36`, `skills/memory/SKILL.md:67-68,229` | Replace `user_scope_db_path()` body to call resolver; update docs. |
| Vault has double-segment `Parai/Parai/` | `skills/dev-log/SKILL.md:16` | Verify on disk before seeding into wizard defaults. |

### Learnings (from learnings-researcher)

No prior `docs/solutions/` entries cover config layering, MCP server creation, or resolver modules for this plugin. Greenfield — no gotchas to avoid from past attempts.

### Memory cases (from plan-phase query)

Three low-reward plan cases returned (all ADR-related, unrelated to this feature). No useful priors.

## Technical Considerations

### Constraints

- **Python 3.10+** (matches `mcp-servers/codex-bridge/server.py` and `skills/memory/scripts/requirements.txt` lower bound). Upper bound 3.12 to match the memory layer's fastembed constraint.
- **stdlib-first.** The resolver module should only depend on `pyyaml` (already vendored via memory's requirements). Avoid pulling `pydantic` or similar — keeps the MCP server lightweight.
- **No network.** Resolver is pure file+env; MCP server never reaches out.
- **Determinism.** Same inputs → same output. No `datetime.now()` in resolver; no randomness.
- **Caching discipline.** Resolver may cache on first load inside one process, but must re-read on every MCP tool invocation only if the file mtime changed (hot-reload nice-to-have; v1 can just reload every call given YAML is tiny).

### Where `.rafayels/` lives: plugin repo vs user project

Two separate use cases share the same resolver:

1. **User project** (`~/Documents/projects/parai-core/`, any repo using the plugin). The user runs `project-config init` here, commits `.rafayels/config.yaml`, and every skill/MCP invocation from this cwd resolves against it. This is the primary case and the motivation for the feature.
2. **Plugin repo** (`rafayels-engineering` itself, for self-dogfooding). The plugin's own dev-log, ADRs, and memory cases need the same config when developing the plugin. The plugin repo commits its own `.rafayels/config.yaml` with the author's values so plugin development keeps working.

These don't conflict because `discover_project_root()` walks up from the caller's cwd — whichever project the user is currently in wins. The plugin installation path (`~/.claude/plugins/cache/rafayels-marketplace/rafayels-engineering/1.2.2/`) is irrelevant at runtime; the resolver never inspects it.

### Project-root discovery

The resolver needs a well-defined "project root" to find `.rafayels/config.yaml`. Ambiguous in MCP context because the server is launched by Claude Code from whichever cwd the plugin host chose.

Algorithm (picks the first that matches):

1. If `RAFAYELS_PROJECT_ROOT` is set, use it.
2. Walk up from `os.getcwd()` looking for `.rafayels/` directory; stop at first hit.
3. Walk up from `os.getcwd()` looking for `.git/` directory; treat as project root.
4. Fall back to `os.getcwd()` (resolver will then fail loudly if no config exists).

Rationale: (1) escape hatch for tests and CI. (2) handles nested workflows (running from a subdir). (3) sensible default. (4) deliberate loud failure — better than silently writing to `$HOME`.

### Path expansion rules

Values read from YAML/env may contain `~` and `$VAR`. The resolver expands both in this order:

1. `os.path.expandvars(value)` — resolves `$HOME`, `$FOO`, `${FOO}`.
2. `os.path.expanduser(value)` — resolves leading `~` and `~user/`.
3. If the result is still relative, resolve against the project root discovered above.
4. Do NOT `Path.resolve()` (would fail on paths that don't exist yet, e.g. `memory.db_path` on first init). Use `os.path.normpath` to clean `..` segments.

Expansion applies only to values of keys whose schema marks them as paths (see schema below). Non-path values pass through untouched.

**Order note** (deepening): `expandvars` before `expanduser` correctly handles both `$HOME/foo` (first pass expands `$HOME`, second is no-op) and `$VAR` when `$VAR="~/foo"` (first pass yields `~/foo`, second expands the leading `~`). Reversing the order breaks the `$VAR=~/foo` case.

### Security: path allowlist

After expansion, each path-typed key's resolved value is checked against a per-key allowlist:

| Key | Allowed prefixes |
|---|---|
| `vault.path` | `$HOME`, explicit user-supplied absolute (no traversal after expansion) |
| `memory.db_path` | `$HOME`, `/tmp` (for tests), explicit absolute |
| `docs.brainstorms_dir`, `docs.plans_dir` | `project_root` (relative paths only; no absolute, no traversal out) |

`..` segments after `normpath` cause `ConfigMalformedError`. This prevents a committed `config.yaml` with `memory.db_path: "../../../etc/passwd"` from writing outside the project.

### YAML parsing hardening

- **`yaml.safe_load` only.** Never `yaml.load`. The plan tests this explicitly (`test_yaml_rejects_python_tags`).
- **Custom `UniqueKeyLoader`** subclass of `SafeLoader` that raises `ConfigMalformedError` on duplicate keys (PyYAML's default silently takes the last one — a common copy-paste bug). ~15 lines. Tested by `test_duplicate_key_raises`.
- **File size cap:** reject YAML files `>64KB` before parsing (defense against billion-laughs-style anchor expansion DoS — still an open PyYAML issue).
- **Reject anchors/aliases** in the config file loader — users don't need `&`/`*` for 6 keys, and they confuse diff review.

### Error taxonomy

All errors inherit from `ProjectConfigError(Exception)`. Two concrete subclasses:

| Exception | When | Message shape |
|---|---|---|
| `ConfigMissingError` | Required key absent, or caller requests unknown key | `"Required config key 'vault.path' is not set. Run 'project-config init' or set RAFAYELS_VAULT_PATH."` Includes `reason: Literal["missing","unknown"]` attribute. Unknown-key errors include `"(Did you mean 'vault.path'?)"` suggestion via `difflib.get_close_matches`. |
| `ConfigMalformedError` | YAML parse error, wrong type, invalid schema, duplicate key, file too large, disallowed path traversal | `"Malformed config at <path>:<line>: <detail>. Expected <type> for '<key>'."` |

`strict=True` mode and `ConfigPathNotFoundError` were dropped in deepening — no v1 caller needs them. Downstream code produces its own "file not found" error with better context when actually opening the path.

### Schema (v1)

Flat dotted keys, nested YAML. Each entry documents type, required-ness, default, and whether path expansion applies. `schema_version: 1` is a required top-level YAML key (added in deepening — cheap, enables future migration).

| Key | Type | Required | Default | Expanded? | Description |
|---|---|:---:|---|:---:|---|
| `schema_version` | int | ✅ | `1` | ❌ | Top-level key. Resolver refuses to load unknown major versions. |
| `vault.path` | str (path) | ✅ | none | ✅ | Obsidian vault root (e.g. `~/Documents/vault/Parai/Parai/`). Consumed by dev-log and vault-researcher. |
| `adr.project` | str | ✅ | none | ❌ | ADR project slug passed to `obsidian-adr` MCP calls (e.g. `parai-core`). |
| `dev_log.subpath` | str (path) | ✅ | none | ❌ | Relative path inside the vault where dev logs live (e.g. `Documentatie/parai-core/Dev Log`). Joined with `vault.path`. |
| `memory.db_path` | str (path) | ❌ | `~/.claude/plugins/rafayels-engineering/memory.db` | ✅ | Where the case-based memory DB lives. Default matches current hardcoded behavior. |
| `docs.brainstorms_dir` | str (path) | ❌ | `docs/brainstorms` | ✅ | Relative to project root. Used by `/workflows:brainstorm` and `/workflows:plan` discovery. |
| `docs.plans_dir` | str (path) | ❌ | `docs/plans` | ✅ | Relative to project root. Used by `/workflows:plan` output. |

Why each key is in scope:

- `vault.path`, `adr.project`, `dev_log.subpath` — currently literal in `skills/dev-log/SKILL.md:16,46` and `skills/using-adr-plugin/SKILL.md:60+`. Non-negotiable.
- `memory.db_path` — soft-override. Default wins unless overridden.
- `docs.brainstorms_dir`, `docs.plans_dir` — already used in workflows but never configurable. Keeping default but exposing knob prevents future drift.

Not in scope (explicitly dropped per brainstorm):

- `default_model` — no current consumer. YAGNI.
- Per-skill overrides — add when a real consumer appears.
- Remote/cloud config — offline-only stays a design principle.

### YAML layout (exact form)

Team defaults — `.rafayels/config.yaml` (committed):

```yaml
# .rafayels/config.yaml — committed team defaults.
# Personal overrides go in .rafayels/config.local.yaml (gitignored).
# Environment variables with RAFAYELS_ prefix override both.
#
# DO NOT store secrets here. Use environment variables or a secret manager.

schema_version: 1

vault:
  path: "~/Documents/vault/Parai/Parai"

adr:
  project: "parai-core"

dev_log:
  subpath: "Documentatie/parai-core/Dev Log"

memory:
  db_path: "~/.claude/plugins/rafayels-engineering/memory.db"

docs:
  brainstorms_dir: "docs/brainstorms"
  plans_dir: "docs/plans"
```

Per-user overrides — `.rafayels/config.local.yaml` (gitignored, optional, same shape, only the keys you want to override):

```yaml
# Example: teammate on a different vault layout
vault:
  path: "/Users/jim/vaults/parai"
dev_log:
  subpath: "Journal/parai-core/Dev Log"
```

Env vars — uppercase, `RAFAYELS_` prefix, dots become underscores. Examples:

- `RAFAYELS_VAULT_PATH=/tmp/vault-fixture`
- `RAFAYELS_ADR_PROJECT=compote`
- `RAFAYELS_MEMORY_DB_PATH=/tmp/memory-test.db`
- `RAFAYELS_DOCS_BRAINSTORMS_DIR=brainstorms`

**Env-overlay build strategy** (from deepening): the resolver iterates over the **known schema keys** and looks up each `RAFAYELS_*` equivalent. It does NOT iterate over `os.environ`. This eliminates the ambiguity between `RAFAYELS_DEV_LOG_SUBPATH = dev.log.subpath` vs `dev_log.subpath` (resolved against the fixed schema) and prevents unknown env vars from silently creating bogus nested keys. Unit-tested via `test_env_overlay_ignores_unknown_keys` and `test_schema_keys_have_unique_env_names`.

### Resolver API shape

`skills/project-config/scripts/resolver.py`:

```python
from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal

SourceLabel = Literal["team", "local", "env", "default"]


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Fully-resolved, path-expanded, validated config."""
    schema_version: int
    vault_path: Path
    adr_project: str
    dev_log_subpath: str               # relative; combine with vault_path
    memory_db_path: Path
    docs_brainstorms_dir: Path
    docs_plans_dir: Path
    project_root: Path                 # where .rafayels/ lives (or fallback)
    source_map: MappingProxyType       # read-only dict[str, SourceLabel]

    def dev_log_path(self) -> Path:
        return self.vault_path / self.dev_log_subpath

    @classmethod
    def from_layers(
        cls,
        team: dict,
        local: dict,
        env: dict,
        project_root: Path,
    ) -> "ProjectConfig":
        """Build from already-parsed layer dicts. Used by tests for direct injection."""
        ...


@functools.lru_cache(maxsize=1)
def load_config(*, project_root: Path | None = None) -> ProjectConfig:
    """Parse, merge, expand, validate. Cached once per process per root.
    Call load_config.cache_clear() for explicit reload (tests, long-running daemons)."""


def discover_project_root(start: Path | None = None) -> Path: ...


def lookup(config: ProjectConfig, dotted_key: str) -> str:
    """Lookup by dotted key name (for CLI/MCP tools). Always returns str —
    callers that need a Path call Path() explicitly. Raises ConfigMissingError
    with reason='unknown' for bad keys, including a difflib suggestion."""


# Exceptions — collapsed from 4 to 2 during deepening (simplicity review).
class ProjectConfigError(Exception):
    """Base for all project-config errors. Carries an optional `fix` hint."""
    fix: str | None = None


class ConfigMissingError(ProjectConfigError):
    """Required key absent OR unknown key requested.
    Carries reason: Literal['missing', 'unknown']."""


class ConfigMalformedError(ProjectConfigError):
    """YAML parse error, duplicate key, wrong type, path-allowlist violation,
    or file exceeds 64KB size cap."""
```

**`sys.path` isolation.** Production consumers (`skills/memory/scripts/db.py`, `mcp-servers/project-config/server.py`) import the resolver via a single module-level helper that mutates `sys.path`:

```python
# at the top of any consumer
def _import_resolver():
    import sys
    from pathlib import Path
    scripts = Path(__file__).resolve().parents[2] / "skills" / "project-config" / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import resolver
    return resolver
```

One place to fix if the layout ever changes. Tests use pytest's `pythonpath` config (`pyproject.toml`) instead, avoiding `sys.path` mutation in test fixtures.

Internal (not part of public API but called by tests):

```python
def _read_yaml(path: Path) -> dict: ...
def _env_overlay() -> dict: ...               # reads RAFAYELS_* env
def _merge(base: dict, overlay: dict) -> dict: ...  # deep merge
def _expand_paths(config: dict, schema: dict, root: Path) -> dict: ...
def _validate(config: dict, schema: dict) -> None: ...
```

### MCP server surface

`mcp-servers/project-config/server.py` — full deepened skeleton (FastMCP research confirmed sync tools are fine, and stdout is reserved for the protocol):

```python
#!/usr/bin/env python3
"""project-config MCP server — resolves layered .rafayels/ config."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Sibling-tree import (one canonical helper in the file)
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "skills" / "project-config" / "scripts"))

from resolver import (  # noqa: E402
    load_config, discover_project_root, lookup,
    ProjectConfigError, SCHEMA,
)
from mcp.server.fastmcp import FastMCP  # noqa: E402

# CRITICAL: MCP stdio uses stdout for the protocol. Logging MUST go to stderr.
logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

mcp = FastMCP("project-config")


def _err(exc: Exception) -> dict:
    return {"status": "error", "error_type": type(exc).__name__,
            "message": str(exc), "fix": getattr(exc, "fix", None)}


@mcp.tool()
def get_config_value(key: str) -> dict:
    """Return one resolved config value. Key is dotted (e.g. 'vault.path')."""
    try:
        cfg = load_config()
        return {"status": "ok", "key": key, "value": lookup(cfg, key),
                "source": cfg.source_map.get(key, "unknown")}
    except ProjectConfigError as e:
        return _err(e)


@mcp.tool()
def get_all_config() -> dict:
    """Return every resolved config key with its value and source layer."""
    try:
        cfg = load_config()
        return {"status": "ok",
                "config": {k: lookup(cfg, k) for k in SCHEMA},
                "source_map": dict(cfg.source_map),
                "project_root": str(cfg.project_root)}
    except ProjectConfigError as e:
        return _err(e)


@mcp.tool()
def get_config_source(key: str) -> dict:
    """Return which layer (team/local/env/default) supplied a key's value."""
    try:
        cfg = load_config()
        return {"status": "ok", "key": key,
                "source": cfg.source_map.get(key, "unknown")}
    except ProjectConfigError as e:
        return _err(e)


@mcp.tool()
def list_config_keys() -> dict:
    """Return the schema — all known keys with type, required-ness, defaults.
    Agents call this to discover config surface without hardcoding key names."""
    return {"status": "ok", "keys": [
        {"key": k, "type": spec["type"].__name__, "required": spec["required"],
         "default": spec.get("default"), "description": spec.get("description", "")}
        for k, spec in SCHEMA.items()
    ]}


@mcp.tool()
def get_project_root() -> dict:
    """Return the discovered project root (where .rafayels/ lives)."""
    try:
        return {"status": "ok", "project_root": str(discover_project_root())}
    except ProjectConfigError as e:
        return _err(e)


@mcp.tool()
def check_config() -> dict:
    """Validate config without raising. Returns ok/error for doctor diagnostics."""
    try:
        load_config.cache_clear()
        load_config()
        return {"status": "ok", "message": "config is valid"}
    except ProjectConfigError as e:
        return _err(e)


@mcp.tool()
def init_config(values: dict, force: bool = False) -> dict:
    """Non-interactive init. `values` is a dict of dotted-key -> string.
    Writes .rafayels/config.yaml. Returns {status, path_written, keys_set}."""
    try:
        from wizard import run_non_interactive  # noqa: E402
        result = run_non_interactive(values, force=force)
        return {"status": "ok", **result}
    except ProjectConfigError as e:
        return _err(e)


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

All tools return dicts with a `status` key (`"ok"` | `"error"`). On error: `{"status": "error", "error_type": ..., "message": ..., "fix": ...}`. Never raise past the MCP boundary — FastMCP v1.26 would wrap it generically, but structured errors give agents more to work with.

### CLI surface

`skills/project-config/scripts/project-config` is a **simple shell wrapper** — just `exec python3 "$(dirname "$0")/cli.py" "$@"`. No interpreter probing needed (unlike the memory wrapper, which exists specifically to find a Python with sqlite-vec loadable extensions). pyyaml works on any stdlib-shipping Python 3.10+.

```
project-config get <key> [--json]
project-config list [--json]                                # all keys + values + source
project-config keys [--json]                                # schema introspection (v1 keys + types + defaults)
project-config check [--json]                               # validates; exits 2 on missing, 3 on malformed
project-config init [--force]                               # interactive wizard
project-config init --non-interactive --set vault.path=... --set adr.project=... [--force]
```

Dropped in deepening: `project-config where` (redundant with `list`'s per-key source) and `project-config path` (debug-only, no planned consumer).

Exit codes (match memory CLI conventions, `skills/memory/SKILL.md:131-137`):

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Not found (key unknown) |
| 2 | Validation / missing required config |
| 3 | Malformed YAML or I/O error |
| 75 | Unavailable (pyyaml missing — EX_TEMPFAIL, workflows tolerate) |

`--json` is a top-level flag (before subcommand), matching memory CLI's explicit fix in `skills/memory/SKILL.md:193-203`.

### Consumption pattern

**Python scripts** import directly:

```python
# skills/memory/scripts/db.py
from pathlib import Path
import sys

# Sibling-import hack matching conftest.py precedent
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "project-config" / "scripts"))
from resolver import load_config

def user_scope_db_path() -> Path:
    config = load_config()
    path = config.memory_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
```

**Markdown skills** call the CLI:

```markdown
<!-- skills/dev-log/SKILL.md -->
Dev logs live at:
$(project-config get dev_log.subpath --json | jq -r '.value')
```

Or as an MCP tool call when the skill runs under an agent:

```
get_config_value({ key: "dev_log.subpath" })
```

**Shell hooks** call the CLI. The plugin's hook system (`hooks/*.sh`) currently has no config needs but if they grow, the same CLI is the answer.

### Init wizard behavior

`project-config init` is the first-run friction reducer. Simplified in deepening — dropped the probing layer per simplicity review.

- **Plain prompts with default values.** Each required key prompts with a hardcoded sensible default in brackets (e.g. `vault.path [~/Documents/vault]:`). User presses enter to accept, types to override. ~30 lines instead of ~150 for probing + prompting.
- **Optional keys are not prompted** — they silently take their default (`memory.db_path`, `docs.*`).
- **Idempotent.** If `.rafayels/config.yaml` already exists, `init` prints "config exists — re-run with `--force` to overwrite" and exits 0.
- **`--non-interactive --set key=value`** for agent-driven bootstrapping. No stdin. All required keys must be supplied via `--set`, or the wizard errors out listing missing keys. Agents call this via the `init_config` MCP tool.
- **Writes team file, not local.** Teammates checking in their config is the point. Users can move keys into `config.local.yaml` themselves if they want.
- **Does NOT create `config.local.yaml`.** Leaves that as a pure opt-in; creating an empty gitignored file would only add noise.
- **`chmod 0600` on any file the wizard writes.** Belt-and-suspenders against accidentally leaking future sensitive additions.

Wizard output shape:

```
$ project-config init
Scanning for likely values…
  ✓ found vault at ~/Documents/vault/Parai/Parai
  ✓ git repo basename is 'rafayels-engineering'

vault.path [~/Documents/vault/Parai/Parai]:
adr.project [rafayels-engineering]: parai-core
dev_log.subpath [Documentatie/parai-core/Dev Log]:
memory.db_path — using default ~/.claude/plugins/rafayels-engineering/memory.db
docs.brainstorms_dir — using default docs/brainstorms
docs.plans_dir — using default docs/plans

Write to .rafayels/config.yaml? [Y/n]:
✓ wrote .rafayels/config.yaml
✓ added .rafayels/config.local.yaml to .gitignore
Done. Validate with: project-config check
```

### Backwards-compat / migration

All in-repo consumers migrate in this PR (no two-sources-of-truth window):

| Consumer | Change |
|---|---|
| `skills/memory/scripts/db.py:34-38` | `user_scope_db_path()` reads `memory.db_path` via resolver. Falls back to existing default if resolver fails — the memory layer must remain runnable even without project-config. |
| `skills/memory/scripts/memory.py` (wrapper) | No change; wrapper invokes Python which imports resolver. |
| `skills/memory/SKILL.md:67-68,229` | Update docs to mention `memory.db_path` is now configurable. |
| `skills/dev-log/SKILL.md:16,46` | Replace literal `/Users/rgardishyan/...` with `$(project-config get vault.path)/<dev_log.subpath>`. |
| `skills/using-adr-plugin/SKILL.md` (14 lines) | Replace every `project: "parai-core"` example with `project: "<adr.project from config>"` and add a "how to read" preface linking to project-config. |
| `.gitignore` | Add `.rafayels/config.local.yaml`. |

Out of scope (follow-up PRs):

- `.opencode/skills/` mirror updates. Noted in a project memory; the mirror is drifting for other reasons and a dedicated cleanup PR is better.
- Any `hooks/*.sh` rewrites — none need config today.

### Resilience to partial failure

The memory layer must run even if project-config is unavailable (missing pyyaml, broken YAML, etc.). Strategy:

```python
# skills/memory/scripts/db.py
import logging
log = logging.getLogger(__name__)

def user_scope_db_path() -> Path:
    try:
        resolver = _import_resolver()
        return resolver.load_config().memory_db_path
    except (ImportError, resolver.ProjectConfigError) as e:
        # Fall back — memory layer is lower in the dep graph than project-config.
        # Log but don't raise: memory layer must not block on config errors.
        log.warning("project-config unavailable (%s); using hardcoded memory DB default", e)
        return Path.home() / ".claude" / "plugins" / "rafayels-engineering" / "memory.db"
```

Two deepening fixes: catch only `ImportError` + `ProjectConfigError` (not bare `Exception` — that would swallow `KeyboardInterrupt`-adjacent bugs), and **log** the fallback so a broken config is diagnosable rather than silent. This is the single exception to "fail loud" and deserves its own ADR.

## Implementation Plan

### Phase 1: Scaffold resolver + tests

**Files to create:**

- `skills/project-config/SKILL.md` — skill metadata + usage docs. Frontmatter:
  ```yaml
  ---
  name: project-config
  description: Resolves project-scoped configuration (vault path, ADR project, memory DB, dev-log subpath, docs dirs) from layered .rafayels/ YAML files + env vars. Used by every skill that touches user paths.
  disable-model-invocation: true
  allowed-tools: Bash, Read, Write
  ---
  ```
  Bash examples in the skill use `${CLAUDE_PLUGIN_ROOT}/skills/project-config/scripts/project-config ...` (matches memory SKILL.md convention).
- `skills/project-config/scripts/resolver.py` — the module.
- `skills/project-config/scripts/cli.py` — argparse-based CLI.
- `skills/project-config/scripts/wizard.py` — init wizard (interactive + `run_non_interactive`).
- `skills/project-config/scripts/requirements.txt` — `pyyaml>=6.0`.
- `skills/project-config/scripts/pyproject.toml` — `[tool.pytest.ini_options] pythonpath = ["."]` to replace any `sys.path` hacks in test setup.
- `skills/project-config/scripts/tests/conftest.py` — fixtures: session-autouse `RAFAYELS_PROJECT_ROOT` pointed at `tmp_path_factory.mktemp`; function-scoped `monkeypatch.delenv` stripping every `RAFAYELS_*` var; `.rafayels/` directory builder helper.
- `skills/project-config/scripts/tests/test_resolver.py` — unit tests (see below).

**Key test cases (TDD) — trimmed to 10 high-value cases per simplicity review + hardened per security review:**

- `test_precedence_env_over_local_over_team` — one test covering all three layers with distinct values.
- `test_missing_required_key_raises` — no `vault.path` anywhere → `ConfigMissingError` with `reason="missing"`.
- `test_unknown_key_raises` — `lookup(cfg, "nonsense.key")` → `ConfigMissingError` with `reason="unknown"` + difflib suggestion.
- `test_malformed_yaml_raises` — broken YAML → `ConfigMalformedError`.
- `test_yaml_rejects_python_tags` — `!!python/object/new:os.system [...]` in YAML → `ConfigMalformedError`. Confirms `safe_load` is wired.
- `test_duplicate_key_raises` — two `vault:` blocks in same file → `ConfigMalformedError`. Confirms `UniqueKeyLoader`.
- `test_yaml_size_cap` — 65KB file rejected before parse.
- `test_path_expansion` — one test covering `~/foo`, `$HOME/foo`, and `$VAR` where `$VAR=~/bar`. Asserts order correctness.
- `test_project_root_discovery` — one test covering env-override > `.rafayels/` > `.git/` > cwd fallback.
- `test_env_overlay_ignores_unknown_keys` — `RAFAYELS_FOOBAR=x` does not create a `foobar` key; schema-driven env read.
- `test_path_allowlist_rejects_traversal` — `memory.db_path: "../../../etc/passwd"` → `ConfigMalformedError`.
- `test_lru_cache_reuses` — two calls to `load_config()` return the same instance; `cache_clear()` invalidates.

### Phase 2: CLI wrapper

**Files to create:**

- `skills/project-config/scripts/project-config` — shell wrapper (matches memory wrapper, reuses interpreter-probing logic).
- `skills/project-config/scripts/cli.py` — argparse-based CLI dispatching to resolver.

**Key CLI test cases:**

- `project-config get vault.path` → prints resolved path, exit 0.
- `project-config get vault.path --json` → prints `{"key": "vault.path", "value": "...", "source": "team"}`.
- `project-config get bogus.key` → exit 1.
- `project-config list --json` → prints every key with source.
- `project-config check` → exit 0 on success, exit 2 on missing required key.
- `project-config where adr.project` → prints `team` or `local` or `env`.

### Phase 3: Init wizard

**Files to create:**

- `skills/project-config/scripts/wizard.py` — probing + prompting logic, pure stdin/stdout.

**Key wizard test cases:**

- `test_wizard_probes_vault` — creates a temp `~/Documents/vault`, asserts pre-fill.
- `test_wizard_refuses_overwrite` — existing `config.yaml` + no `--force` → exits 0 with message.
- `test_wizard_force_overwrites` — `--force` replaces existing file.
- `test_wizard_writes_gitignore_entry` — asserts root `.gitignore` contains `.rafayels/config.local.yaml`.
- Integration: run the wizard with mocked stdin, assert resulting YAML parses and validates.

### Phase 4: MCP server

**Files to create:**

- `mcp-servers/project-config/server.py` — FastMCP server.
- `mcp-servers/project-config/README.md` — match `codex-bridge/README.md` layout.
- `mcp-servers/project-config/requirements.txt` — `mcp`, `pyyaml>=6.0`.

**Modifications:**

- `.claude-plugin/plugin.json` — add `project-config` entry to `mcpServers`:
  ```json
  "project-config": {
    "type": "stdio",
    "command": "python3",
    "args": ["mcp-servers/project-config/server.py"]
  }
  ```

**`mcp-servers/project-config/requirements.txt`:**

```
mcp>=1.26,<2.0
pyyaml>=6.0
```

Same `mcp` pin applied to `mcp-servers/codex-bridge/requirements.txt` in the same PR — closes the "FastMCP version mismatch" risk already listed.

**Manual smoke tests (can't unit-test MCP stdio easily):**

- Launch the server directly (`python3 mcp-servers/project-config/server.py`) and send a raw MCP `tools/call` request via stdin (see codex-bridge docs for shape).
- In a real Claude Code session, verify the tools appear and return expected values.

### Phase 5: Migrate consumers

Work in this order — low-risk to high-risk:

1. **`.gitignore`** — add `.rafayels/config.local.yaml`. One line.
2. **Seed `.rafayels/config.yaml`** for the plugin repo itself (the author's current values, for plugin-dev dogfooding — see "Where `.rafayels/` lives"). Commit it so plugin devs can immediately run the workflows in this repo.
3. **`skills/memory/scripts/db.py:34-38`** — rewrite `user_scope_db_path()` with the try/except escape hatch. Run full memory test suite; must stay green.
4. **`skills/memory/SKILL.md:67-68,229`** — update docs.
5. **`skills/dev-log/SKILL.md:16,46`** — replace literal paths with CLI-based expansion. Test by running the skill mentally through a dev-log creation flow.
6. **`skills/using-adr-plugin/SKILL.md` (14 occurrences)** — templating pass. Replace `"parai-core"` with a clear placeholder + a preface explaining how to read actual value.

### Phase 6: Docs + release

- `README.md` — new section "Project config" with usage examples.
- `CLAUDE.md` — update if it mentions hardcoded paths.
- Dev log entry describing the feature + migration.
- Possible ADR for "Layered project config via `.rafayels/`".

## Alternatives Considered

### A. Env-var-only (no resolver module)

Each consumer reads `RAFAYELS_VAULT_PATH`, `RAFAYELS_ADR_PROJECT`, etc. directly. Pros: no new code. Cons: every consumer reinvents expansion/validation, there's no schema, no first-run story, no place to add `check`/`where`/`init`. Rejected.

### B. Single flat YAML, no layering

`.rafayels.yaml` only, no local override, no env. Pros: simpler. Cons: teammates can't override personal paths without dirtying git. Fails the core motivation. Rejected.

### C. Rust / Go resolver

Matches the plugin's broader toolkit leanings. Pros: fast startup. Cons: startup for a YAML read is already sub-millisecond in Python; every other script in the plugin is Python; would require shipping a binary. Rejected for YAGNI.

### D. Use existing `pydantic-settings` or `dynaconf`

Full-featured config libraries. Pros: battle-tested. Cons: extra dependency weight for ~100 lines of custom logic; our schema is tiny and stable. Rejected.

### E. MCP-only, no CLI

Skip the CLI; Python scripts shell out to the MCP server. Pros: fewer files. Cons: MCP stdio is awkward to invoke from shell hooks and from non-Claude contexts; `/workflows:` markdown is hard to template. Rejected — brainstorm explicitly chose both front-ends.

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Migrating memory DB path breaks active memory layer in this repo | Medium | High | Try/except fallback to current hardcoded default in `user_scope_db_path`. Run full memory test suite after migration. Keep a clear rollback commit. |
| `.rafayels/config.yaml` clashes with an existing convention | Low | Low | Grep marketplace for `.rafayels` — none found. Name is plugin-scoped. |
| Path expansion picks up unwanted env var in YAML value | Low | Medium | Expansion only runs on path-typed keys per schema. Non-path keys (like `adr.project`) pass through unchanged. |
| Init wizard probes and pre-fills the wrong vault | Medium | Low | User reviews every prompt before write. Wizard never writes silently. |
| `.opencode/` mirror stays broken | High | Low | Explicitly out of scope. Documented in follow-up. Not a regression — the mirror is already drifting. |
| FastMCP version mismatch between codex-bridge and project-config | Low | Low | Pin `mcp>=X` in both requirements.txt files. Share a version via comment or constants file if needed later. |
| Teammates forget to commit `.rafayels/config.yaml` | Low | Medium | `project-config check` exits non-zero if the file is missing. CI/hooks can call it. |
| Wizard overwrites user's manual edits | Low | Medium | `--force` required to overwrite. Default behavior is no-op when file exists. |
| Tests pass locally but fail on teammate's box (path differences) | Medium | Medium | Tests use tmpdir fixtures, never touch real `~/` or project `.rafayels/`. `RAFAYELS_PROJECT_ROOT` env var scopes every test. |

## Success Metrics

- **Zero hardcoded paths** in `skills/**/*.md`, `skills/**/*.py`, `hooks/*.sh` after merge (grep check in CI or `project-config check --strict`).
- **Fresh-clone-to-working-plugin time < 2 minutes** for a new teammate: clone, `project-config init`, done.
- **No regressions** in memory layer tests.
- **One PR, one migration** — no two-sources-of-truth window.

## Resolved During Deepen

- **Config caching.** `@functools.lru_cache(maxsize=1)` on `load_config()`. `cache_clear()` available for tests and explicit reload. Skip mtime watching — matches pydantic-settings/dynaconf ecosystem norm.
- **Schema versioning.** `schema_version: 1` required at YAML top level. Unlocks future migration at near-zero cost.
- **Example config file.** Not needed — `project-config init` generates a real, committed file.
- **Extracting to its own plugin.** Defer until a second consumer exists.
- **TOML vs YAML.** Stay on YAML — memory layer uses YAML, splitting config formats inside one plugin is worse than YAML's edge cases. Use `UniqueKeyLoader` + `safe_load` + size cap to close the gap with TOML's strictness.
- **`strict=True` mode and `ConfigPathNotFoundError`.** Dropped. No v1 consumer; downstream code produces better "file not found" errors when actually opening paths.

## Still Open (Post-Deepen)

- **Line-number preservation in error messages.** `ruamel.yaml` or position-tracking loader. Probably v2; adds polish to "malformed config at line X" errors. Flagged as nice-to-have.
- **Config hot-reload on file-mtime change.** Today: manual `cache_clear()` or server restart. Open if users find restart friction annoying.
- **ADR for memory-layer fallback**. The one principled exception to "fail loud" deserves its own decision record.

## Pseudo-code / File Layout

```
.worktrees/feat/project-config-mcp/
├── .claude-plugin/
│   └── plugin.json                                  # EDIT: add project-config mcpServer
├── .rafayels/
│   └── config.yaml                                  # NEW: committed team defaults
├── .gitignore                                       # EDIT: add .rafayels/config.local.yaml
├── mcp-servers/
│   ├── codex-bridge/                                # unchanged
│   └── project-config/
│       ├── README.md                                # NEW
│       ├── requirements.txt                         # NEW: mcp, pyyaml>=6.0
│       └── server.py                                # NEW: FastMCP wrapper
├── skills/
│   ├── memory/
│   │   ├── scripts/db.py                            # EDIT: user_scope_db_path uses resolver
│   │   └── SKILL.md                                 # EDIT: docs for memory.db_path key
│   ├── dev-log/SKILL.md                             # EDIT: remove literal paths
│   ├── using-adr-plugin/SKILL.md                    # EDIT: template parai-core references
│   └── project-config/
│       ├── SKILL.md                                 # NEW
│       └── scripts/
│           ├── project-config                       # NEW: shell wrapper
│           ├── cli.py                               # NEW: argparse CLI
│           ├── resolver.py                          # NEW: the module
│           ├── wizard.py                            # NEW: init wizard
│           ├── requirements.txt                     # NEW: pyyaml>=6.0
│           └── tests/
│               ├── conftest.py                      # NEW: fixtures
│               ├── test_resolver.py                 # NEW
│               ├── test_cli.py                      # NEW
│               └── test_wizard.py                   # NEW
└── docs/
    ├── brainstorms/2026-04-16-project-config-mcp-brainstorm.md   # already exists
    └── plans/2026-04-16-feat-project-config-mcp-server-plan.md   # this file
```

## Testing Approach

- **Unit (pytest, sibling-import):** resolver precedence, path expansion, validation, exceptions.
- **Integration:** CLI end-to-end with `subprocess.run` + tmpdir `.rafayels/`.
- **Smoke (manual):** launch MCP server, invoke each tool via Claude Code in a dev session.
- **Regression:** full memory test suite runs after db.py edit; zero new failures allowed.
- **Fresh-clone simulation:** `git worktree` on a clean tmpdir, run `project-config init` with mocked stdin, verify the wizard + resolver + memory flow end-to-end.

## Definition of Done

- All acceptance criteria checked.
- Memory layer tests green.
- `project-config check --strict` exits 0 in this repo after init.
- PR description links the brainstorm and this plan.
- Dev log entry posted.
- ADR created for the fallback behavior in `user_scope_db_path` (memory layer bypasses project-config on failure — this is the one explicit violation of "fail loud" and deserves its own record).
