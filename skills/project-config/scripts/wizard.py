from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

import resolver


def run_non_interactive(values: dict, force: bool = False) -> dict:
    """Write `.rafayels/config.yaml` from dotted-key input values."""

    project_root = resolver.discover_project_root()
    config_dir = project_root / ".rafayels"
    config_path = config_dir / "config.yaml"

    if config_path.exists() and not force:
        raise FileExistsError(f"{config_path} already exists. Re-run with force=True to overwrite.")

    flat_values = _flatten_values(values)
    for key, spec in resolver.SCHEMA.items():
        if key not in flat_values and spec["default"] is not None:
            flat_values[key] = spec["default"]

    payload = resolver._unflatten(flat_values)
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    os.chmod(config_path, 0o600)

    return {
        "path_written": str(config_path),
        "keys_set": sorted(flat_values),
    }


def run_interactive() -> dict:
    raise NotImplementedError("Phase 3")


def _flatten_values(values: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in values.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten_values(value, dotted))
        else:
            flat[dotted] = value
    return flat
