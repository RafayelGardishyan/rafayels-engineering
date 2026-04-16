from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, TextIO

import yaml

import resolver

_VAULT_CANDIDATES = [
    "~/Documents/vault/Parai/Parai",
    "~/Documents/vault",
]
_GITIGNORE_ENTRY = ".rafayels/config.local.yaml"
_PROMPT_KEYS = ["vault.path", "adr.project", "dev_log.subpath"]


def run_non_interactive(values: dict, force: bool = False) -> dict:
    """Write `.rafayels/config.yaml` from dotted-key input values."""

    project_root = resolver.discover_project_root()
    flat_values = _flatten_values(values)
    flat_values["schema_version"] = flat_values.get("schema_version", resolver._SCHEMA_VERSION)
    return _write_config(project_root, flat_values, force=force)


def run_interactive(
    *,
    stream_in: TextIO | None = None,
    stream_out: TextIO | None = None,
    force: bool = False,
) -> dict:
    """Interactive wizard — prompts for required keys, writes config.yaml."""

    stdin = stream_in if stream_in is not None else sys.stdin
    stdout = stream_out if stream_out is not None else sys.stdout
    project_root = resolver.discover_project_root()

    config_path = project_root / ".rafayels" / "config.yaml"
    if config_path.exists() and not force:
        stdout.write(
            f"{config_path} already exists. Re-run with --force to overwrite.\n"
        )
        stdout.flush()
        return {"path_written": None, "keys_set": [], "skipped": True}

    defaults = _compute_defaults(project_root)
    flat_values: dict[str, Any] = {"schema_version": resolver._SCHEMA_VERSION}
    for key in _PROMPT_KEYS:
        flat_values[key] = _prompt(key, defaults[key], stdin, stdout)

    result = _write_config(project_root, flat_values, force=True)
    stdout.write(f"wrote {result['path_written']}\n")
    stdout.flush()
    return result


def _compute_defaults(project_root: Path) -> dict[str, str]:
    return {
        "vault.path": _probe_vault_default(),
        "adr.project": project_root.name,
        "dev_log.subpath": "Dev Log",
    }


def _probe_vault_default() -> str:
    for candidate in _VAULT_CANDIDATES:
        expanded = Path(os.path.expanduser(candidate))
        if expanded.is_dir():
            return candidate
    return _VAULT_CANDIDATES[-1]


def _prompt(key: str, default: str, stream_in: TextIO, stream_out: TextIO) -> str:
    stream_out.write(f"{key} [{default}]: ")
    stream_out.flush()
    line = stream_in.readline()
    if not line:
        return default
    value = line.rstrip("\r\n").strip()
    return value if value else default


def _write_config(project_root: Path, flat_values: dict[str, Any], *, force: bool) -> dict:
    config_dir = project_root / ".rafayels"
    config_path = config_dir / "config.yaml"
    if config_path.exists() and not force:
        raise FileExistsError(
            f"{config_path} already exists. Re-run with force=True to overwrite."
        )

    for key, spec in resolver.SCHEMA.items():
        if key not in flat_values and spec["default"] is not None:
            flat_values[key] = spec["default"]

    payload = resolver._unflatten(flat_values)
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    os.chmod(config_path, 0o600)

    _ensure_gitignore_entry(project_root)

    return {
        "path_written": str(config_path),
        "keys_set": sorted(flat_values),
    }


def _ensure_gitignore_entry(project_root: Path) -> None:
    path = project_root / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if any(line.strip() == _GITIGNORE_ENTRY for line in existing.splitlines()):
        return
    new_content = existing
    if new_content and not new_content.endswith("\n"):
        new_content += "\n"
    new_content += f"{_GITIGNORE_ENTRY}\n"
    path.write_text(new_content, encoding="utf-8")


def _flatten_values(values: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in values.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten_values(value, dotted))
        else:
            flat[dotted] = value
    return flat
