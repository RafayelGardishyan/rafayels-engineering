"""Shared fixtures for memory-proposer tests."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Add memory-proposer scripts + memory scripts to path
SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent.parent / "memory" / "scripts"))


@pytest.fixture()
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "proposer-test.db"


@pytest.fixture()
def conn(tmp_db_path: Path, monkeypatch):
    from db import connect, init_schema

    # Patch embedder in both capture and retrieve
    import embedder

    def fake_embed(texts, prefer_daemon=True):
        return [
            np.asarray(
                [(hash(t) % 100) / 100.0 + (i / 384.0) for i in range(384)],
                dtype=np.float32,
            )
            for t in texts
        ]

    monkeypatch.setattr(embedder, "embed", fake_embed)
    import capture

    monkeypatch.setattr(capture, "embed", fake_embed)

    c = connect(tmp_db_path)
    init_schema(c)
    yield c
    c.close()
