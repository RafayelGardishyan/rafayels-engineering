"""Concurrency tests: WAL mode + BEGIN IMMEDIATE + retry handles concurrent writes.

These tests spawn two threads writing to the same DB and verify no corruption.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from capture import write_case
from db import connect, init_schema


@pytest.fixture()
def shared_db_path(tmp_path: Path, monkeypatch) -> Path:
    """A temp DB path plus patched embedder for concurrent tests."""
    import numpy as np

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

    # Initialize schema once
    db_path = tmp_path / "concurrent.db"
    conn = connect(db_path)
    init_schema(conn)
    conn.close()
    return db_path


def test_concurrent_writes_do_not_corrupt(shared_db_path: Path):
    """Two threads writing simultaneously should both succeed."""
    results: list[int] = []
    errors: list[Exception] = []

    def writer(idx: int):
        try:
            conn = connect(shared_db_path)
            for i in range(5):
                case_id = write_case(
                    conn,
                    phase="plan",
                    query=f"thread-{idx}-case-{i}",
                )
                results.append(case_id)
            conn.close()
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=writer, args=(1,))
    t2 = threading.Thread(target=writer, args=(2,))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)

    assert not errors, f"concurrent writes errored: {errors}"
    assert len(results) == 10  # 2 threads x 5 cases each

    # Verify all cases are in the DB
    conn = connect(shared_db_path, readonly=True)
    count = conn.execute("SELECT COUNT(*) FROM cases_raw").fetchone()[0]
    assert count == 10
    conn.close()
