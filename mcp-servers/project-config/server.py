#!/usr/bin/env python3
"""Project-config MCP server.

Exposes the layered `.rafayels/config.yaml` resolver as a FastMCP stdio
server so agents can read project configuration without shelling out.

Design notes:
- All tools return plain dicts with a `status` key (`"ok"` | `"error"`).
  Structured errors let agents inspect `error_type` and act on `fix`
  hints without parsing tracebacks.
- MCP stdio uses stdout for the protocol, so logging goes to stderr.
- The resolver module lives in `skills/project-config/scripts/`; we
  prepend that directory to sys.path rather than package-installing it,
  matching the codex-bridge approach of colocated stdlib-only servers.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
_RESOLVER_DIR = _PLUGIN_ROOT / "skills" / "project-config" / "scripts"
sys.path.insert(0, str(_RESOLVER_DIR))

from resolver import (  # noqa: E402
    SCHEMA,
    ProjectConfigError,
    discover_project_root,
    load_config,
    lookup,
)
from wizard import run_non_interactive  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

mcp = FastMCP("project-config")


def _err(exc: Exception) -> dict:
    return {
        "status": "error",
        "error_type": type(exc).__name__,
        "message": str(exc),
        "fix": getattr(exc, "fix", None),
    }


@mcp.tool()
def get_config_value(key: str) -> dict:
    """Return one resolved config value. `key` is dotted (e.g. 'vault.path')."""
    try:
        cfg = load_config()
        return {
            "status": "ok",
            "key": key,
            "value": lookup(cfg, key),
            "source": cfg.source_map.get(key, "unknown"),
        }
    except ProjectConfigError as exc:
        return _err(exc)


@mcp.tool()
def get_all_config() -> dict:
    """Return every resolved config key with its value and source layer."""
    try:
        cfg = load_config()
        return {
            "status": "ok",
            "config": {key: lookup(cfg, key) for key in SCHEMA},
            "source_map": dict(cfg.source_map),
            "project_root": str(cfg.project_root),
        }
    except ProjectConfigError as exc:
        return _err(exc)


@mcp.tool()
def get_config_source(key: str) -> dict:
    """Return which layer (team/local/env/default) supplied a key's value."""
    try:
        cfg = load_config()
        if key not in cfg.source_map:
            return _err(
                ProjectConfigError(
                    f"Unknown config key '{key}'.",
                    fix="Call list_config_keys to discover valid keys.",
                )
            )
        return {
            "status": "ok",
            "key": key,
            "source": cfg.source_map[key],
        }
    except ProjectConfigError as exc:
        return _err(exc)


@mcp.tool()
def list_config_keys() -> dict:
    """Return the schema — all known keys with type, required-ness, defaults.

    Agents call this to discover the config surface without hardcoding
    key names.
    """
    return {
        "status": "ok",
        "keys": [
            {
                "key": key,
                "type": spec["type"].__name__,
                "required": spec["required"],
                "default": spec.get("default"),
                "description": spec.get("description", ""),
            }
            for key, spec in SCHEMA.items()
        ],
    }


@mcp.tool()
def get_project_root() -> dict:
    """Return the discovered project root (where .rafayels/ lives)."""
    try:
        return {"status": "ok", "project_root": str(discover_project_root())}
    except ProjectConfigError as exc:
        return _err(exc)


@mcp.tool()
def check_config() -> dict:
    """Validate config without raising. Returns ok/error for doctor diagnostics."""
    try:
        load_config.cache_clear()
        load_config()
        return {"status": "ok", "message": "config is valid"}
    except ProjectConfigError as exc:
        return _err(exc)


@mcp.tool()
def init_config(values: dict, force: bool = False) -> dict:
    """Non-interactive init. `values` is a dict of dotted-key -> string.

    Writes `.rafayels/config.yaml`. Returns {status, path_written, keys_set}.
    """
    try:
        result = run_non_interactive(values, force=force)
        return {"status": "ok", **result}
    except FileExistsError as exc:
        return {
            "status": "error",
            "error_type": "FileExistsError",
            "message": str(exc),
            "fix": "Call init_config again with force=True to overwrite.",
        }
    except ProjectConfigError as exc:
        return _err(exc)


if __name__ == "__main__":
    mcp.run(transport="stdio")
