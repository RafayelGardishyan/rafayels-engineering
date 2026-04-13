"""Shared pytest fixtures for memory skill tests."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

# Make sibling modules importable from tests/
SCRIPTS = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture()
def tmp_db_path(tmp_path: Path) -> Path:
    """Return a temporary DB path."""
    return tmp_path / "test-memory.db"


@pytest.fixture()
def conn(tmp_db_path: Path, monkeypatch):
    """Provide an initialized DB connection with schema, using a mock embedder.

    Monkeypatches `embedder.embed` to return deterministic fake vectors so
    tests don't depend on fastembed being installed.
    """
    from db import connect, init_schema

    # Patch embedder to return deterministic fake vectors (384-dim)
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
    # Also patch the one in capture and retrieve modules
    import capture
    import retrieve

    monkeypatch.setattr(capture, "embed", fake_embed)
    monkeypatch.setattr(retrieve, "embed", fake_embed)

    c = connect(tmp_db_path)
    init_schema(c)
    yield c
    c.close()


@pytest.fixture()
def deterministic_vec():
    """A deterministic 384-dim unit vector for tests."""
    rng = np.random.default_rng(42)
    v = rng.random(384, dtype=np.float32)
    return v / np.linalg.norm(v)
