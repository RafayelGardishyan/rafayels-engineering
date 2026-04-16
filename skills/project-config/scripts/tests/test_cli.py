from __future__ import annotations

import json
from pathlib import Path

import cli
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


def _seed_valid_config(
    rafayels_root: Path,
    monkeypatch,
    *,
    vault_path: str = "~/team-vault",
) -> Path:
    home = rafayels_root / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    write_yaml(rafayels_root / ".rafayels" / "config.yaml", _full_config(vault_path=vault_path))
    return home / "team-vault"


def test_get_plain(rafayels_root: Path, monkeypatch, capsys) -> None:
    expected_path = _seed_valid_config(rafayels_root, monkeypatch)

    exit_code = cli.main(["get", "vault.path"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == f"{expected_path}\n"
    assert captured.err == ""


def test_get_json(rafayels_root: Path, monkeypatch, capsys) -> None:
    expected_path = _seed_valid_config(rafayels_root, monkeypatch)

    exit_code = cli.main(["get", "vault.path", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload == {"key": "vault.path", "value": str(expected_path), "source": "team"}


def test_get_unknown_key(rafayels_root: Path, monkeypatch, capsys) -> None:
    _seed_valid_config(rafayels_root, monkeypatch)

    exit_code = cli.main(["get", "bogus.key"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Unknown config key" in captured.err
    assert "Did you mean" in captured.err


def test_list_json(rafayels_root: Path, monkeypatch, capsys) -> None:
    expected_path = _seed_valid_config(rafayels_root, monkeypatch)

    exit_code = cli.main(["list", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert set(payload["config"]) == set(resolver.SCHEMA)
    assert set(payload["source_map"]) == set(resolver.SCHEMA)
    assert payload["config"]["vault.path"] == str(expected_path)
    assert payload["source_map"]["vault.path"] == "team"
    assert payload["project_root"] == str(rafayels_root)


def test_check_passes_on_valid(rafayels_root: Path, monkeypatch, capsys) -> None:
    _seed_valid_config(rafayels_root, monkeypatch)

    valid_exit_code = cli.main(["check"])
    valid_output = capsys.readouterr()

    write_yaml(
        rafayels_root / ".rafayels" / "config.yaml",
        {
            "schema_version": 1,
            "adr": {"project": "team-adr"},
            "dev_log": {"subpath": "team/dev-log"},
        },
    )
    resolver.load_config.cache_clear()

    missing_exit_code = cli.main(["check"])
    missing_output = capsys.readouterr()

    assert valid_exit_code == 0
    assert valid_output.out == ""
    assert valid_output.err == ""
    assert missing_exit_code == 2
    assert "Required config key 'vault.path' is not set" in missing_output.err


def test_where(rafayels_root: Path, monkeypatch, capsys) -> None:
    _seed_valid_config(rafayels_root, monkeypatch)

    exit_code = cli.main(["where", "vault.path"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() in {"team", "local", "env", "default"}
    assert captured.err == ""
