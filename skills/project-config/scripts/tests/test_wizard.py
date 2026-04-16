from __future__ import annotations

import io
import os
from pathlib import Path

import pytest
import yaml

import resolver
import wizard


def test_wizard_probes_vault(
    rafayels_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_home = rafayels_root / "fake_home"
    (fake_home / "Documents" / "vault").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("USERPROFILE", raising=False)

    stdout = io.StringIO()
    stdin = io.StringIO("\n\n\n")

    result = wizard.run_interactive(stream_in=stdin, stream_out=stdout)

    assert result["path_written"] is not None
    assert "vault.path [~/Documents/vault]:" in stdout.getvalue()

    data = yaml.safe_load(
        (rafayels_root / ".rafayels" / "config.yaml").read_text(encoding="utf-8")
    )
    assert data["vault"]["path"] == "~/Documents/vault"
    assert data["adr"]["project"] == rafayels_root.name


def test_wizard_refuses_overwrite(rafayels_root: Path) -> None:
    config_path = rafayels_root / ".rafayels" / "config.yaml"
    original = "schema_version: 1\n"
    config_path.write_text(original, encoding="utf-8")

    stdout = io.StringIO()
    stdin = io.StringIO()

    result = wizard.run_interactive(stream_in=stdin, stream_out=stdout)

    assert result == {"path_written": None, "keys_set": [], "skipped": True}
    assert "already exists" in stdout.getvalue()
    assert "--force" in stdout.getvalue()
    assert config_path.read_text(encoding="utf-8") == original


def test_wizard_force_overwrites(rafayels_root: Path) -> None:
    config_path = rafayels_root / ".rafayels" / "config.yaml"
    config_path.write_text("schema_version: 1\n", encoding="utf-8")

    stdin = io.StringIO("/tmp/vault\nmy-project\nDev Log\n")
    stdout = io.StringIO()

    result = wizard.run_interactive(stream_in=stdin, stream_out=stdout, force=True)

    assert result["path_written"] == str(config_path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert data["vault"]["path"] == "/tmp/vault"
    assert data["adr"]["project"] == "my-project"
    assert data["dev_log"]["subpath"] == "Dev Log"


def test_wizard_writes_gitignore_entry(rafayels_root: Path) -> None:
    stdin = io.StringIO("/tmp/vault\nmy-project\nDev Log\n")
    stdout = io.StringIO()

    wizard.run_interactive(stream_in=stdin, stream_out=stdout)

    gitignore = rafayels_root / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text(encoding="utf-8")
    assert ".rafayels/config.local.yaml" in content

    wizard.run_interactive(
        stream_in=io.StringIO("/tmp/vault2\np2\nLog2\n"),
        stream_out=io.StringIO(),
        force=True,
    )
    assert gitignore.read_text(encoding="utf-8").count(".rafayels/config.local.yaml") == 1


def test_wizard_integration_produces_valid_config(rafayels_root: Path) -> None:
    stdin = io.StringIO("/tmp/my-vault\nmy-project\nDev Log\n")
    stdout = io.StringIO()

    result = wizard.run_interactive(stream_in=stdin, stream_out=stdout)
    assert result["path_written"] is not None

    config = resolver.load_config()
    assert str(config.vault_path) == "/tmp/my-vault"
    assert config.adr_project == "my-project"
    assert config.dev_log_subpath == "Dev Log"
    assert config.schema_version == 1

    mode = os.stat(result["path_written"]).st_mode & 0o777
    assert mode == 0o600
