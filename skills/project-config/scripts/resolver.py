from __future__ import annotations

import difflib
import functools
import os
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

import yaml

SourceLabel = Literal["team", "local", "env", "default"]

_MAX_YAML_BYTES = 64 * 1024
_SCHEMA_VERSION = 1
_CONFIG_DIR = ".rafayels"
_TEAM_CONFIG = "config.yaml"
_LOCAL_CONFIG = "config.local.yaml"

SCHEMA: dict[str, dict[str, Any]] = {
    "schema_version": {
        "type": int,
        "required": True,
        "default": 1,
        "expand_path": False,
        "description": "Top-level config schema version.",
    },
    "vault.path": {
        "type": str,
        "required": True,
        "default": None,
        "expand_path": True,
        "allowed_prefixes": ["$HOME", "absolute"],
        "description": "Obsidian vault root.",
    },
    "adr.project": {
        "type": str,
        "required": True,
        "default": None,
        "expand_path": False,
        "description": "ADR project slug.",
    },
    "dev_log.subpath": {
        "type": str,
        "required": True,
        "default": None,
        "expand_path": False,
        "description": "Relative dev-log path inside the vault.",
    },
    "memory.db_path": {
        "type": str,
        "required": False,
        "default": "~/.claude/plugins/rafayels-engineering/memory.db",
        "expand_path": True,
        "allowed_prefixes": ["$HOME", "/tmp", "absolute"],
        "description": "Case-based memory SQLite database path.",
    },
    "docs.brainstorms_dir": {
        "type": str,
        "required": False,
        "default": "docs/brainstorms",
        "expand_path": True,
        "allowed_prefixes": ["project_root"],
        "description": "Project-local brainstorm directory.",
    },
    "docs.plans_dir": {
        "type": str,
        "required": False,
        "default": "docs/plans",
        "expand_path": True,
        "allowed_prefixes": ["project_root"],
        "description": "Project-local plans directory.",
    },
}


class ProjectConfigError(Exception):
    """Base for all project-config errors."""

    fix: str | None

    def __init__(self, message: str, *, fix: str | None = None) -> None:
        super().__init__(message)
        self.fix = fix


class ConfigMissingError(ProjectConfigError):
    """Raised for missing required keys or unknown lookup keys."""

    reason: Literal["missing", "unknown"]

    def __init__(
        self,
        message: str,
        *,
        reason: Literal["missing", "unknown"],
        fix: str | None = None,
    ) -> None:
        super().__init__(message, fix=fix)
        self.reason = reason


class ConfigMalformedError(ProjectConfigError):
    """Raised for invalid config files or invalid resolved values."""


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate keys and anchors."""

    def compose_node(self, parent: yaml.nodes.Node | None, index: int) -> yaml.nodes.Node:
        if self.check_event(yaml.AliasEvent):
            raise ConfigMalformedError("YAML anchors and aliases are not allowed.")
        event = self.peek_event()
        if getattr(event, "anchor", None) is not None:
            raise ConfigMalformedError("YAML anchors and aliases are not allowed.")
        return super().compose_node(parent, index)

    def construct_mapping(
        self,
        node: yaml.nodes.MappingNode,
        deep: bool = False,
    ) -> dict[Any, Any]:
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                already_seen = key in mapping
            except TypeError as exc:
                raise ConfigMalformedError("Config keys must be hashable scalars.") from exc
            if already_seen:
                raise ConfigMalformedError(f"Duplicate key {key!r} is not allowed.")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Fully-resolved, path-expanded, validated config."""

    schema_version: int
    vault_path: Path
    adr_project: str
    dev_log_subpath: str
    memory_db_path: Path
    docs_brainstorms_dir: Path
    docs_plans_dir: Path
    project_root: Path
    source_map: MappingProxyType

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
        team_flat = _flatten(team)
        local_flat = _flatten(local)
        env_flat = _flatten(env)

        merged = _merge(team, local)
        merged = _merge(merged, env)
        merged_flat = _flatten(merged)
        source_map: dict[str, SourceLabel] = {}

        for key, spec in SCHEMA.items():
            if key in env_flat:
                source_map[key] = "env"
                continue
            if key in local_flat:
                source_map[key] = "local"
                continue
            if key in team_flat:
                source_map[key] = "team"
                continue
            if spec["default"] is not None:
                merged_flat[key] = spec["default"]
                source_map[key] = "default"

        expanded = _expand_paths(_unflatten(merged_flat), SCHEMA, project_root)
        _validate(expanded, SCHEMA)
        flat = _flatten(expanded)

        return cls(
            schema_version=flat["schema_version"],
            vault_path=flat["vault.path"],
            adr_project=flat["adr.project"],
            dev_log_subpath=flat["dev_log.subpath"],
            memory_db_path=flat["memory.db_path"],
            docs_brainstorms_dir=flat["docs.brainstorms_dir"],
            docs_plans_dir=flat["docs.plans_dir"],
            project_root=project_root,
            source_map=MappingProxyType(dict(source_map)),
        )


@functools.lru_cache(maxsize=1)
def load_config(*, project_root: Path | None = None) -> ProjectConfig:
    """Parse, merge, expand, and validate the project config."""

    root = _normalize_root(project_root or discover_project_root())
    config_dir = root / _CONFIG_DIR
    team = _read_yaml(config_dir / _TEAM_CONFIG)
    local = _read_yaml(config_dir / _LOCAL_CONFIG)
    env = _env_overlay()
    return ProjectConfig.from_layers(team=team, local=local, env=env, project_root=root)


def discover_project_root(start: Path | None = None) -> Path:
    """Discover the project root using env override, .rafayels, .git, then cwd."""

    env_root = os.environ.get("RAFAYELS_PROJECT_ROOT")
    if env_root:
        return _normalize_root(Path(os.path.normpath(os.path.expanduser(os.path.expandvars(env_root)))))

    base = _normalize_root(start or Path.cwd())
    for candidate in (base, *base.parents):
        if (candidate / _CONFIG_DIR).is_dir():
            return candidate
    for candidate in (base, *base.parents):
        if (candidate / ".git").is_dir():
            return candidate
    return base


def lookup(config: ProjectConfig, dotted_key: str) -> str:
    """Lookup by dotted schema key and return its resolved string value."""

    if dotted_key not in SCHEMA:
        suggestion = difflib.get_close_matches(dotted_key, SCHEMA.keys(), n=1)
        message = f"Unknown config key '{dotted_key}'."
        if suggestion:
            message = f"{message} Did you mean '{suggestion[0]}'?"
        raise ConfigMissingError(
            message,
            reason="unknown",
            fix="Run `project-config keys` to list valid config keys.",
        )

    value = getattr(config, dotted_key.replace(".", "_"))
    return str(value)


def _read_yaml(path: Path) -> dict:
    """Read one YAML config file into a nested dict."""

    if not path.exists():
        return {}
    if path.stat().st_size > _MAX_YAML_BYTES:
        raise ConfigMalformedError(f"Malformed config at {path}: file exceeds 64KB limit.")

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigMalformedError(f"Malformed config at {path}: {exc}.") from exc

    loader = UniqueKeyLoader(text)
    try:
        data = loader.get_single_data()
    except ConfigMalformedError as exc:
        raise ConfigMalformedError(f"Malformed config at {path}: {exc}", fix=exc.fix) from exc
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark
        location = f"{path}:{mark.line + 1}:{mark.column + 1}" if mark is not None else str(path)
        detail = exc.problem or str(exc)
        raise ConfigMalformedError(f"Malformed config at {location}: {detail}.") from exc
    except yaml.YAMLError as exc:
        raise ConfigMalformedError(f"Malformed config at {path}: {exc}.") from exc
    finally:
        loader.dispose()

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigMalformedError(f"Malformed config at {path}: expected a mapping at the document root.")
    return data


def _env_overlay() -> dict:
    """Build a nested env overlay by iterating the known schema keys only."""

    flat: dict[str, Any] = {}
    for key, spec in SCHEMA.items():
        env_name = _env_name(key)
        raw_value = os.environ.get(env_name)
        if raw_value is None:
            continue
        if spec["type"] is int:
            try:
                flat[key] = int(raw_value)
            except ValueError as exc:
                raise ConfigMalformedError(
                    f"Malformed config in {env_name}: expected int for '{key}'."
                ) from exc
            continue
        flat[key] = raw_value
    return _unflatten(flat)


def _merge(base: dict, overlay: dict) -> dict:
    """Deep-merge two nested mappings without mutating either input."""

    result: dict[str, Any] = {}
    for key, value in base.items():
        if isinstance(value, dict):
            result[key] = _merge(value, {})
        else:
            result[key] = value
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        elif isinstance(value, dict):
            result[key] = _merge({}, value)
        else:
            result[key] = value
    return result


def _expand_paths(config: dict, schema: dict, root: Path) -> dict:
    """Expand configured path values and enforce per-key allowlists."""

    flat = _flatten(config)
    expanded_flat = dict(flat)

    for key, spec in schema.items():
        if not spec.get("expand_path") or key not in flat:
            continue

        raw_value = flat[key]
        if not isinstance(raw_value, str):
            continue

        expanded = os.path.expandvars(raw_value)
        expanded = os.path.expanduser(expanded)
        normalized = os.path.normpath(expanded)
        normalized_path = Path(normalized)

        if ".." in normalized_path.parts:
            raise ConfigMalformedError(
                f"Malformed config value for '{key}': path traversal is not allowed."
            )

        raw_was_absolute = normalized_path.is_absolute()
        if raw_was_absolute:
            candidate = normalized_path
        else:
            candidate = Path(os.path.normpath(str(root / normalized_path)))

        _check_allowed_prefixes(
            key=key,
            path=candidate,
            allowed_prefixes=spec.get("allowed_prefixes", []),
            project_root=root,
            raw_was_absolute=raw_was_absolute,
        )
        expanded_flat[key] = candidate

    return _unflatten(expanded_flat)


def _validate(config: dict, schema: dict) -> None:
    """Validate keys, types, requiredness, and schema-version compatibility."""

    flat = _flatten(config)
    unknown_keys = sorted(set(flat) - set(schema))
    if unknown_keys:
        raise ConfigMalformedError(
            f"Unknown config key(s): {', '.join(repr(key) for key in unknown_keys)}."
        )

    for key, spec in schema.items():
        if key not in flat:
            if spec["required"]:
                env_name = _env_name(key)
                raise ConfigMissingError(
                    (
                        f"Required config key '{key}' is not set. "
                        f"Run 'project-config init' or set {env_name}."
                    ),
                    reason="missing",
                    fix=f"Set {env_name} or add '{key}' to .rafayels/{_TEAM_CONFIG}.",
                )
            continue

        value = flat[key]
        if spec.get("expand_path"):
            if not isinstance(value, Path):
                raise ConfigMalformedError(f"Expected path value for '{key}'.")
            if not value.is_absolute():
                raise ConfigMalformedError(f"Expected absolute path for '{key}'.")
            continue

        expected_type = spec["type"]
        if expected_type is int:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ConfigMalformedError(f"Expected int for '{key}'.")
        elif expected_type is str:
            if not isinstance(value, str):
                raise ConfigMalformedError(f"Expected str for '{key}'.")

    schema_version = flat["schema_version"]
    if schema_version != _SCHEMA_VERSION:
        raise ConfigMalformedError(
            f"Unsupported schema_version {schema_version!r}; expected {_SCHEMA_VERSION}."
        )

    dev_log_subpath = Path(flat["dev_log.subpath"])
    if dev_log_subpath.is_absolute() or ".." in dev_log_subpath.parts:
        raise ConfigMalformedError("Malformed config value for 'dev_log.subpath': must be relative.")


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in data.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten(value, dotted))
        else:
            flat[dotted] = value
    return flat


def _unflatten(flat: dict[str, Any]) -> dict[str, Any]:
    nested: dict[str, Any] = {}
    for dotted_key, value in flat.items():
        cursor = nested
        parts = dotted_key.split(".")
        for part in parts[:-1]:
            next_value = cursor.get(part)
            if not isinstance(next_value, dict):
                next_value = {}
                cursor[part] = next_value
            cursor = next_value
        cursor[parts[-1]] = value
    return nested


def _env_name(dotted_key: str) -> str:
    return f"RAFAYELS_{dotted_key.replace('.', '_').upper()}"


def _normalize_root(path: Path) -> Path:
    return Path(os.path.normpath(str(path)))


def _check_allowed_prefixes(
    *,
    key: str,
    path: Path,
    allowed_prefixes: list[str],
    project_root: Path,
    raw_was_absolute: bool,
) -> None:
    if "project_root" in allowed_prefixes:
        if raw_was_absolute:
            raise ConfigMalformedError(
                f"Malformed config value for '{key}': absolute paths are not allowed."
            )
        if not _is_relative_to(path, project_root):
            raise ConfigMalformedError(
                f"Malformed config value for '{key}': path must stay within {project_root}."
            )
        return

    if "absolute" in allowed_prefixes and path.is_absolute():
        return

    if "$HOME" in allowed_prefixes:
        home = Path(os.path.expanduser("~"))
        if _is_relative_to(path, home):
            return

    if "/tmp" in allowed_prefixes and _is_relative_to(path, Path("/tmp")):
        return

    raise ConfigMalformedError(
        f"Malformed config value for '{key}': path '{path}' is outside the allowed prefixes."
    )


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
    except ValueError:
        return False
    return True
