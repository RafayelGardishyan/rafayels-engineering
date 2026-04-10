"""Tests for retrieve.py: cold-start, MMR, decay, cap, query integration."""

from __future__ import annotations

import numpy as np
import pytest

from capture import add_signal, promote, write_case
from db import now
from retrieve import (
    DECAY_TAU_DAYS,
    DEFAULT_K,
    RETRIEVAL_CAP_RATIO,
    apply_decay,
    format_for_injection,
    mmr_rerank,
    query,
    results_to_json,
    retrieval_cap_penalty,
    should_retrieve,
)


# ---------------------------------------------------------------------------
# should_retrieve — cold-start check
# ---------------------------------------------------------------------------


def test_should_retrieve_false_on_empty_bank(conn):
    assert should_retrieve(conn, "plan", k=3) is False


def test_should_retrieve_false_below_threshold(conn):
    # Write 5 active cases (need k*3 = 9 for should_retrieve to return True)
    for i in range(5):
        cid = write_case(conn, phase="plan", query=f"test {i}")
        add_signal(conn, case_id=cid, signal_type="merge", value=1.0)
        add_signal(conn, case_id=cid, signal_type="approval", value=1.0)
    assert should_retrieve(conn, "plan", k=3) is False


def test_should_retrieve_true_above_threshold(conn):
    # Need 9 active+ cases for k=3
    for i in range(10):
        cid = write_case(conn, phase="plan", query=f"test {i}")
        add_signal(conn, case_id=cid, signal_type="merge", value=1.0)
        add_signal(conn, case_id=cid, signal_type="approval", value=1.0)
    assert should_retrieve(conn, "plan", k=3) is True


# ---------------------------------------------------------------------------
# apply_decay
# ---------------------------------------------------------------------------


def test_apply_decay_no_age():
    assert apply_decay(0.8, 0) == pytest.approx(0.8)


def test_apply_decay_reduces_with_age():
    fresh = 0.8
    aged = apply_decay(fresh, 60)
    assert aged < fresh


def test_apply_decay_tau_half_life():
    # At tau*ln(2) days, reward should be halved
    import math

    half_life_days = DECAY_TAU_DAYS * math.log(2)
    assert apply_decay(1.0, half_life_days) == pytest.approx(0.5, abs=0.01)


# ---------------------------------------------------------------------------
# retrieval_cap_penalty
# ---------------------------------------------------------------------------


def test_retrieval_cap_penalty_under_sample(conn):
    """Penalty is 0 when there aren't enough retrievals to assess."""
    assert retrieval_cap_penalty(conn, 1) == 0.0


def test_retrieval_cap_penalty_under_cap(conn):
    """Case appearing in <= 30% of retrievals gets no penalty."""
    # Create enough retrievals with a case appearing ~10% of the time
    for i in range(20):
        case_id = 1 if i == 0 else 2
        conn.execute(
            "INSERT INTO retrievals (case_id, phase, distance, rank, created) VALUES (?, 'plan', 0.1, 1, ?)",
            (case_id, now()),
        )
    # Case 1 appears 1/20 = 5% — no penalty
    assert retrieval_cap_penalty(conn, 1) == 0.0


def test_retrieval_cap_penalty_over_cap(conn):
    """Case exceeding 30% of retrievals gets penalized."""
    # 15 out of 20 retrievals are case 1 (75%)
    for i in range(20):
        case_id = 1 if i < 15 else 2
        conn.execute(
            "INSERT INTO retrievals (case_id, phase, distance, rank, created) VALUES (?, 'plan', 0.1, 1, ?)",
            (case_id, now()),
        )
    assert retrieval_cap_penalty(conn, 1) > 0.0


# ---------------------------------------------------------------------------
# MMR rerank
# ---------------------------------------------------------------------------


def test_mmr_returns_all_when_candidates_fewer_than_k():
    query_vec = np.ones(384, dtype=np.float32)
    query_vec /= np.linalg.norm(query_vec)
    candidates = [
        (1, query_vec, 0.1, 0.9),
        (2, query_vec, 0.2, 0.8),
    ]
    result = mmr_rerank(query_vec, candidates, k=5)
    assert len(result) == 2


def test_mmr_selects_diverse_candidates():
    """Given 3 near-duplicates + 1 outlier, MMR should pick at least one distinct item."""
    # 3 nearly-identical vectors
    base = np.random.default_rng(1).random(384, dtype=np.float32)
    base /= np.linalg.norm(base)
    near_dup_1 = base + np.random.default_rng(2).normal(0, 0.01, 384).astype(np.float32)
    near_dup_2 = base + np.random.default_rng(3).normal(0, 0.01, 384).astype(np.float32)
    near_dup_1 /= np.linalg.norm(near_dup_1)
    near_dup_2 /= np.linalg.norm(near_dup_2)

    # Outlier
    outlier = np.random.default_rng(42).random(384, dtype=np.float32)
    outlier /= np.linalg.norm(outlier)

    query_vec = base

    candidates = [
        (1, base, 0.0, 1.0),
        (2, near_dup_1, 0.02, 0.98),
        (3, near_dup_2, 0.03, 0.97),
        (4, outlier, 0.5, 0.5),
    ]
    selected = mmr_rerank(query_vec, candidates, k=2, lambda_=0.3)
    ids = {s[0] for s in selected}
    # With low λ (diversity weighted), outlier should be selected over near-dups
    assert 1 in ids  # highest relevance
    assert 4 in ids or 2 not in ids  # diversity forced the 2nd pick


# ---------------------------------------------------------------------------
# query — integration
# ---------------------------------------------------------------------------


def test_query_returns_empty_below_cold_start(conn):
    # Only 2 cases — below k*3 threshold
    for i in range(2):
        cid = write_case(conn, phase="plan", query=f"test {i}")
        add_signal(conn, case_id=cid, signal_type="merge", value=1.0)
        add_signal(conn, case_id=cid, signal_type="approval", value=1.0)
    results = query(conn, text="anything", phase="plan", k=3)
    assert results == []


def test_query_returns_cases_above_cold_start(conn):
    # Create enough active cases
    for i in range(10):
        cid = write_case(conn, phase="plan", query=f"test {i}")
        add_signal(conn, case_id=cid, signal_type="merge", value=1.0)
        add_signal(conn, case_id=cid, signal_type="approval", value=1.0)

    results = query(conn, text="test", phase="plan", k=3)
    assert len(results) <= 3
    assert len(results) > 0


def test_query_excludes_specified_case_ids(conn):
    for i in range(10):
        cid = write_case(conn, phase="plan", query=f"test {i}")
        add_signal(conn, case_id=cid, signal_type="merge", value=1.0)
        add_signal(conn, case_id=cid, signal_type="approval", value=1.0)

    all_results = query(conn, text="test", phase="plan", k=3)
    if not all_results:
        pytest.skip("query returned no results")

    first_id = all_results[0].case.case_id
    results = query(
        conn, text="test", phase="plan", k=3, exclude_case_ids=[first_id]
    )
    assert all(r.case.case_id != first_id for r in results)


def test_query_excludes_quarantine_by_default(conn):
    # Write cases but don't add signals — they stay in quarantine
    for i in range(10):
        write_case(conn, phase="plan", query=f"test {i}")

    # Bank has 10 quarantined cases. Since none are active+promoted, cold-start
    # check passes on active count (0) — should return empty.
    results = query(conn, text="test", phase="plan", k=3)
    assert results == []


def test_query_logs_retrievals(conn):
    for i in range(10):
        cid = write_case(conn, phase="plan", query=f"test {i}")
        add_signal(conn, case_id=cid, signal_type="merge", value=1.0)
        add_signal(conn, case_id=cid, signal_type="approval", value=1.0)

    before = conn.execute("SELECT COUNT(*) FROM retrievals").fetchone()[0]
    query(conn, text="test", phase="plan", k=3, workflow_run_id="test-run-1")
    after = conn.execute("SELECT COUNT(*) FROM retrievals").fetchone()[0]
    assert after > before


# ---------------------------------------------------------------------------
# Format for injection
# ---------------------------------------------------------------------------


def test_format_for_injection_empty():
    assert format_for_injection([]) == ""


def test_results_to_json_shape(conn):
    for i in range(10):
        cid = write_case(conn, phase="plan", query=f"test {i}")
        add_signal(conn, case_id=cid, signal_type="merge", value=1.0)
        add_signal(conn, case_id=cid, signal_type="approval", value=1.0)
    results = query(conn, text="test", phase="plan", k=3)
    if results:
        data = results_to_json(results)
        assert isinstance(data, list)
        assert "case_id" in data[0]
        assert "final_score" in data[0]
