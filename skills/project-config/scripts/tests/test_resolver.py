from __future__ import annotations

from pathlib import Path

import pytest

import resolver
from tests.conftest import write_yaml


def _full_config(*, vault_path: str = "~/team-vault") -> dict:
    return {
        "schema_version": 1,
        "vault": {"path": vault_path},
        "adr": {"project": "team-adr"},
        "dev_log": {"subpath": "team/dev-log"},
        "memory": {"db_path": "$HOME/team-memory.db"},
        "docs": {
            "brainstorms_dir": "docs/team-brainstorms",
            "plans_dir": "docs/team-plans",
        },
    }


def test_precedence_env_over_local_over_team(
    rafayels_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = rafayels_root / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    write_yaml(rafayels_root / ".rafayels" / "config.yaml", _full_config())
    write_yaml(
        rafayels_root / ".rafayels" / "config.local.yaml",
        {
            "adr": {"project": "local-adr"},
            "dev_log": {"subpath": "local/dev-log"},
            "docs": {"brainstorms_dir": "docs/local-brainstorms"},
        },
    )
    monkeypatch.setenv("RAFAYELS_VAULT_PATH", "$HOME/env-vault")
    monkeypatch.setenv("RAFAYELS_DOCS_PLANS_DIR", "docs/env-plans")

    cfg = resolver.load_config()

    assert cfg.vault_path == home / "env-vault"
    assert cfg.adr_project == "local-adr"
    assert cfg.dev_log_subpath == "local/dev-log"
    assert cfg.memory_db_path == home / "team-memory.db"
    assert cfg.docs_brainstorms_dir == rafayels_root / "docs/local-brainstorms"
    assert cfg.docs_plans_dir == rafayels_root / "docs/env-plans"
    assert cfg.source_map["vault.path"] == "env"
    assert cfg.source_map["adr.project"] == "local"
    assert cfg.source_map["memory.db_path"] == "team"
    assert cfg.source_map["docs.plans_dir"] == "env"


def test_missing_required_key_raises(rafayels_root: Path) -> None:
    write_yaml(
        rafayels_root / ".rafayels" / "config.yaml",
        {
            "schema_version": 1,
            "adr": {"project": "team-adr"},
            "dev_log": {"subpath": "team/dev-log"},
        },
    )

    with pytest.raises(resolver.ConfigMissingError) as exc_info:
        resolver.load_config()

    assert exc_info.value.reason == "missing"


def test_unknown_key_raises(
    rafayels_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = rafayels_root / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    write_yaml(rafayels_root / ".rafayels" / "config.yaml", _full_config())

    cfg = resolver.load_config()

    with pytest.raises(resolver.ConfigMissingError) as exc_info:
        resolver.lookup(cfg, "vault.pth")

    assert exc_info.value.reason == "unknown"
    assert "Did you mean" in str(exc_info.value)


def test_malformed_yaml_raises(rafayels_root: Path) -> None:
    config_path = rafayels_root / ".rafayels" / "config.yaml"
    config_path.write_text("schema_version: 1\nvault: [\n", encoding="utf-8")

    with pytest.raises(resolver.ConfigMalformedError):
        resolver.load_config()


def test_yaml_rejects_python_tags(rafayels_root: Path) -> None:
    config_path = rafayels_root / ".rafayels" / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "vault:",
                "  path: !!python/object/apply:os.system ['echo nope']",
                "adr:",
                "  project: team-adr",
                "dev_log:",
                "  subpath: team/dev-log",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(resolver.ConfigMalformedError):
        resolver.load_config()


def test_duplicate_key_raises(rafayels_root: Path) -> None:
    config_path = rafayels_root / ".rafayels" / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "vault:",
                "  path: /tmp/one",
                "vault:",
                "  path: /tmp/two",
                "adr:",
                "  project: team-adr",
                "dev_log:",
                "  subpath: team/dev-log",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(resolver.ConfigMalformedError):
        resolver.load_config()


def test_yaml_size_cap(rafayels_root: Path) -> None:
    config_path = rafayels_root / ".rafayels" / "config.yaml"
    config_path.write_text("x" * ((64 * 1024) + 1024), encoding="utf-8")

    with pytest.raises(resolver.ConfigMalformedError):
        resolver.load_config()


def test_path_expansion(rafayels_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = rafayels_root / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CUSTOM_PATH", "~/bar")

    tilde_expanded = resolver._expand_paths(
        {"vault": {"path": "~/foo"}},
        resolver.SCHEMA,
        rafayels_root,
    )
    home_expanded = resolver._expand_paths(
        {"memory": {"db_path": "$HOME/foo.db"}},
        resolver.SCHEMA,
        rafayels_root,
    )
    var_then_tilde = resolver._expand_paths(
        {"vault": {"path": "$CUSTOM_PATH"}},
        resolver.SCHEMA,
        rafayels_root,
    )

    assert tilde_expanded["vault"]["path"] == home / "foo"
    assert home_expanded["memory"]["db_path"] == home / "foo.db"
    assert var_then_tilde["vault"]["path"] == home / "bar"


def test_project_root_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_root = tmp_path / "env-root"
    env_root.mkdir()
    monkeypatch.setenv("RAFAYELS_PROJECT_ROOT", str(env_root))
    assert resolver.discover_project_root(start=tmp_path / "somewhere") == env_root

    monkeypatch.delenv("RAFAYELS_PROJECT_ROOT", raising=False)
    rafayels_root = tmp_path / "with-rafayels"
    (rafayels_root / ".rafayels").mkdir(parents=True)
    nested_rafayels = rafayels_root / "a" / "b"
    nested_rafayels.mkdir(parents=True)
    assert resolver.discover_project_root(start=nested_rafayels) == rafayels_root

    git_root = tmp_path / "with-git"
    (git_root / ".git").mkdir(parents=True)
    nested_git = git_root / "c" / "d"
    nested_git.mkdir(parents=True)
    assert resolver.discover_project_root(start=nested_git) == git_root

    cwd_fallback = tmp_path / "plain" / "subdir"
    cwd_fallback.mkdir(parents=True)
    assert resolver.discover_project_root(start=cwd_fallback) == cwd_fallback


def test_env_overlay_ignores_unknown_keys(
    rafayels_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = rafayels_root / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RAFAYELS_FOOBAR", "x")
    write_yaml(rafayels_root / ".rafayels" / "config.yaml", _full_config())

    overlay = resolver._env_overlay()
    cfg = resolver.load_config()

    assert overlay == {}
    assert cfg.adr_project == "team-adr"
    assert "foobar" not in cfg.source_map


def test_path_allowlist_rejects_traversal(rafayels_root: Path) -> None:
    data = _full_config()
    data["memory"]["db_path"] = "../../../etc/passwd"
    write_yaml(rafayels_root / ".rafayels" / "config.yaml", data)

    with pytest.raises(resolver.ConfigMalformedError):
        resolver.load_config()


def test_lru_cache_reuses(
    rafayels_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = rafayels_root / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    config_path = rafayels_root / ".rafayels" / "config.yaml"
    write_yaml(config_path, _full_config())

    first = resolver.load_config()
    second = resolver.load_config()

    write_yaml(
        config_path,
        {
            **_full_config(),
            "adr": {"project": "updated-adr"},
        },
    )
    resolver.load_config.cache_clear()
    third = resolver.load_config()

    assert first is second
    assert third is not first
    assert third.adr_project == "updated-adr"
