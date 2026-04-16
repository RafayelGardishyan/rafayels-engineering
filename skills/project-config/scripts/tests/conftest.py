from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

import resolver


@pytest.fixture(autouse=True)
def clear_rafayels_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [name for name in os.environ if name.startswith("RAFAYELS_")]:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def clear_load_config_cache() -> None:
    resolver.load_config.cache_clear()
    yield
    resolver.load_config.cache_clear()


@pytest.fixture()
def rafayels_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".rafayels").mkdir()
    monkeypatch.setenv("RAFAYELS_PROJECT_ROOT", str(tmp_path))
    return tmp_path


def write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
