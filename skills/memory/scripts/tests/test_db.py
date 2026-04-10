"""Tests for db.py: connection, schema, PRAGMAs, dataclasses, VectorIndex."""

from __future__ import annotations

import sqlite3
import struct

import numpy as np
import pytest

from db import (
    EMBEDDING_DIM,
    Case,
    Config,
    SqliteVecIndex,
    connect,
    detect_project,
    init_schema,
    now,
    write_transaction,
)


def test_connect_applies_pragmas(tmp_db_path):
    conn = connect(tmp_db_path)
    try:
        # Check critical PRAGMAs
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_init_schema_creates_all_tables(tmp_db_path):
    conn = connect(tmp_db_path)
    init_schema(conn)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
        ).fetchall()
    }
    assert "cases_raw" in tables
    assert "cases_vec" in tables
    assert "signals" in tables
    assert "retrievals" in tables
    assert "patterns" in tables
    assert "case_links" in tables
    assert "meta" in tables
    conn.close()


def test_init_schema_seeds_meta(tmp_db_path):
    conn = connect(tmp_db_path)
    init_schema(conn)
    config = Config.load(conn)
    assert config.schema_version == 1
    assert config.embedding_dim == EMBEDDING_DIM
    assert config.embedding_model == "BAAI/bge-small-en-v1.5"
    conn.close()


def test_config_assert_compatible(tmp_db_path):
    conn = connect(tmp_db_path)
    init_schema(conn)
    config = Config.load(conn)
    # Should not raise
    config.assert_compatible()
    # Should raise on mismatch
    with pytest.raises(ValueError, match="model"):
        config.assert_compatible(expected_model="wrong-model")
    with pytest.raises(ValueError, match="dim"):
        config.assert_compatible(expected_dim=512)
    conn.close()


def test_vector_index_roundtrip(conn, deterministic_vec):
    """Upsert + search roundtrip."""
    vec_index = SqliteVecIndex(conn)

    # Need a case_id that exists in cases_raw for the FK
    cursor = conn.execute(
        """
        INSERT INTO cases_raw (
            phase, status, reward, created, updated, query
        ) VALUES ('plan', 'active', 0.7, ?, ?, 'test')
        """,
        (now(), now()),
    )
    case_id = cursor.lastrowid

    vec_index.upsert(case_id, "plan", deterministic_vec)

    results = vec_index.search(deterministic_vec, phase="plan", k=5)
    assert len(results) >= 1
    assert results[0][0] == case_id
    assert results[0][1] < 0.01  # self-match has near-zero distance


def test_vector_index_phase_filter(conn, deterministic_vec):
    """Searching one phase doesn't return cases from another."""
    vec_index = SqliteVecIndex(conn)

    for phase in ["plan", "review"]:
        cursor = conn.execute(
            """
            INSERT INTO cases_raw (phase, status, reward, created, updated, query)
            VALUES (?, 'active', 0.7, ?, ?, ?)
            """,
            (phase, now(), now(), f"test {phase}"),
        )
        vec_index.upsert(cursor.lastrowid, phase, deterministic_vec)

    plan_results = vec_index.search(deterministic_vec, phase="plan", k=10)
    review_results = vec_index.search(deterministic_vec, phase="review", k=10)

    assert len(plan_results) == 1
    assert len(review_results) == 1
    assert plan_results[0][0] != review_results[0][0]


def test_check_constraints_reject_bad_phase(conn):
    """Schema CHECK should reject invalid phase."""
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO cases_raw (phase, status, reward, created, updated, query)
            VALUES ('invalid_phase', 'active', 0.7, ?, ?, 'test')
            """,
            (now(), now()),
        )


def test_check_constraints_reject_bad_reward(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO cases_raw (phase, status, reward, created, updated, query)
            VALUES ('plan', 'active', 1.5, ?, ?, 'test')
            """,
            (now(), now()),
        )


def test_fk_cascade_delete_signals(conn):
    """Deleting a case cascades to signals."""
    cursor = conn.execute(
        """
        INSERT INTO cases_raw (phase, status, reward, created, updated, query)
        VALUES ('plan', 'active', 0.7, ?, ?, 'test')
        """,
        (now(), now()),
    )
    case_id = cursor.lastrowid

    conn.execute(
        "INSERT INTO signals (case_id, signal_type, value, created) VALUES (?, 'merge', 1.0, ?)",
        (case_id, now()),
    )

    conn.execute("DELETE FROM cases_raw WHERE case_id = ?", (case_id,))
    remaining = conn.execute(
        "SELECT COUNT(*) FROM signals WHERE case_id = ?", (case_id,)
    ).fetchone()[0]
    assert remaining == 0


def test_quarantine_promotion_trigger(conn):
    """Two positive signals promotes a quarantined case to active."""
    cursor = conn.execute(
        """
        INSERT INTO cases_raw (phase, status, reward, created, updated, query)
        VALUES ('plan', 'quarantine', 0.5, ?, ?, 'test')
        """,
        (now(), now()),
    )
    case_id = cursor.lastrowid

    # First positive signal — still quarantine
    conn.execute(
        "INSERT INTO signals (case_id, signal_type, value, created) VALUES (?, 'merge', 1.0, ?)",
        (case_id, now()),
    )
    status = conn.execute(
        "SELECT status FROM cases_raw WHERE case_id = ?", (case_id,)
    ).fetchone()[0]
    assert status == "quarantine"

    # Second positive signal — promoted to active
    conn.execute(
        "INSERT INTO signals (case_id, signal_type, value, created) VALUES (?, 'approval', 1.0, ?)",
        (case_id, now()),
    )
    status = conn.execute(
        "SELECT status FROM cases_raw WHERE case_id = ?", (case_id,)
    ).fetchone()[0]
    assert status == "active"


def test_reward_recompute_trigger(conn):
    """Signal insert auto-recomputes reward via trigger."""
    cursor = conn.execute(
        """
        INSERT INTO cases_raw (phase, status, reward, created, updated, query)
        VALUES ('plan', 'active', 0.5, ?, ?, 'test')
        """,
        (now(), now()),
    )
    case_id = cursor.lastrowid

    conn.execute(
        "INSERT INTO signals (case_id, signal_type, value, created) VALUES (?, 'merge', 1.0, ?)",
        (case_id, now()),
    )

    reward = conn.execute(
        "SELECT reward FROM cases_raw WHERE case_id = ?", (case_id,)
    ).fetchone()[0]
    # With a single merge signal of +1.0: (0.40 * 1.0) / 0.40 = 1.0 -> mapped to 1.0
    assert reward == pytest.approx(1.0, abs=0.01)


def test_write_transaction_commits(conn):
    with write_transaction(conn):
        conn.execute(
            """
            INSERT INTO cases_raw (phase, status, reward, created, updated, query)
            VALUES ('plan', 'active', 0.5, ?, ?, 'committed')
            """,
            (now(), now()),
        )
    count = conn.execute(
        "SELECT COUNT(*) FROM cases_raw WHERE query = 'committed'"
    ).fetchone()[0]
    assert count == 1


def test_detect_project_returns_string():
    # Should return a non-empty string regardless of git state
    result = detect_project()
    assert isinstance(result, str)
    assert len(result) > 0


def test_case_from_row(conn):
    conn.execute(
        """
        INSERT INTO cases_raw (
            phase, status, reward, created, updated, query, title, tags
        ) VALUES ('plan', 'active', 0.8, ?, ?, 'test query', 'test title', '["a","b"]')
        """,
        (now(), now()),
    )
    row = conn.execute(
        "SELECT * FROM cases_raw WHERE query = 'test query'"
    ).fetchone()
    case = Case.from_row(row)
    assert case.phase == "plan"
    assert case.title == "test title"
    assert case.reward == 0.8
    assert case.tags == ["a", "b"]
