"""Tests for capture.py: composite_reward (pure), write_case, add_signal, prune, promote."""

from __future__ import annotations

import pytest

from capture import (
    NEUTRAL_REWARD,
    SIGNAL_WEIGHTS,
    add_signal,
    composite_reward,
    composite_reward_for_case,
    delete_case,
    enforce_token_cap,
    link_cases,
    promote,
    prune,
    update_case,
    write_case,
)
from db import now


# ---------------------------------------------------------------------------
# composite_reward — pure function tests
# ---------------------------------------------------------------------------


def test_composite_reward_empty_signals_returns_neutral():
    assert composite_reward([]) == NEUTRAL_REWARD


def test_composite_reward_perfect_merge():
    # Single merge signal of +1.0: weighted mean = +1.0 -> mapped to 1.0
    assert composite_reward([("merge", 1.0)]) == pytest.approx(1.0)


def test_composite_reward_perfect_failure():
    # Single merge signal of -1.0: weighted mean = -1.0 -> mapped to 0.0
    assert composite_reward([("merge", -1.0)]) == pytest.approx(0.0)


def test_composite_reward_mixed_signals():
    # merge=+1.0 (w=0.4), review=-1.0 (w=0.2): weighted mean = (0.4*1.0 + 0.2*-1.0) / 0.6 = 0.333
    # mapped: (0.333 + 1.0) / 2.0 = 0.667
    result = composite_reward([("merge", 1.0), ("review", -1.0)])
    assert result == pytest.approx((0.333 + 1.0) / 2.0, abs=0.01)


def test_composite_reward_multiple_same_type():
    # Two merge signals, one +1.0 and one -1.0: average = 0.0, mapped = 0.5
    result = composite_reward([("merge", 1.0), ("merge", -1.0)])
    assert result == pytest.approx(0.5, abs=0.01)


def test_composite_reward_ignores_unknown_types():
    # Unknown signal type should be ignored, falling back to neutral
    assert composite_reward([("unknown_type", 1.0)]) == NEUTRAL_REWARD


def test_composite_reward_clipped_to_unit_interval():
    # Even with extreme values, reward stays in [0, 1]
    for sig_type in SIGNAL_WEIGHTS:
        assert 0.0 <= composite_reward([(sig_type, 1.0)]) <= 1.0
        assert 0.0 <= composite_reward([(sig_type, -1.0)]) <= 1.0


# ---------------------------------------------------------------------------
# enforce_token_cap
# ---------------------------------------------------------------------------


def test_enforce_token_cap_short_text_unchanged():
    text = "This is a short summary."
    assert enforce_token_cap(text, max_tokens=300) == text


def test_enforce_token_cap_long_text_truncated():
    # Generate a text well over 300 tokens
    text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 100
    result = enforce_token_cap(text, max_tokens=50)
    assert len(result) < len(text)


# ---------------------------------------------------------------------------
# write_case
# ---------------------------------------------------------------------------


def test_write_case_creates_quarantined_case(conn):
    case_id = write_case(
        conn,
        phase="plan",
        query="How to structure the memory layer",
        title="Test case",
        plan="Use sqlite-vec + fastembed",
        outcome="Worked well",
        tags=["test", "memory"],
    )
    row = conn.execute(
        "SELECT * FROM cases_raw WHERE case_id = ?", (case_id,)
    ).fetchone()
    assert row["status"] == "quarantine"
    assert row["phase"] == "plan"
    assert row["title"] == "Test case"


def test_write_case_stores_embedding(conn):
    case_id = write_case(
        conn,
        phase="plan",
        query="How to structure the memory layer",
    )
    row = conn.execute(
        "SELECT case_id FROM cases_vec WHERE case_id = ?", (case_id,)
    ).fetchone()
    assert row is not None


def test_write_case_rejects_invalid_phase(conn):
    with pytest.raises(ValueError, match="phase"):
        write_case(conn, phase="invalid", query="test")


def test_write_case_auto_injection_summary(conn):
    case_id = write_case(
        conn,
        phase="plan",
        query="test query",
        plan="test plan",
        outcome="test outcome",
    )
    row = conn.execute(
        "SELECT injection_summary FROM cases_raw WHERE case_id = ?", (case_id,)
    ).fetchone()
    assert row["injection_summary"] is not None
    assert "test" in row["injection_summary"]


# ---------------------------------------------------------------------------
# add_signal
# ---------------------------------------------------------------------------


def test_add_signal_inserts_row(conn):
    case_id = write_case(conn, phase="plan", query="test")
    add_signal(conn, case_id=case_id, signal_type="merge", value=1.0, source="pr:#1")
    count = conn.execute(
        "SELECT COUNT(*) FROM signals WHERE case_id = ?", (case_id,)
    ).fetchone()[0]
    assert count == 1


def test_add_signal_rejects_invalid_type(conn):
    case_id = write_case(conn, phase="plan", query="test")
    with pytest.raises(ValueError, match="signal_type"):
        add_signal(conn, case_id=case_id, signal_type="invalid", value=0.5)


def test_add_signal_rejects_out_of_range_value(conn):
    case_id = write_case(conn, phase="plan", query="test")
    with pytest.raises(ValueError, match="value"):
        add_signal(conn, case_id=case_id, signal_type="merge", value=1.5)


def test_two_positive_signals_promotes_case(conn):
    case_id = write_case(conn, phase="plan", query="test")
    add_signal(conn, case_id=case_id, signal_type="merge", value=1.0)
    add_signal(conn, case_id=case_id, signal_type="approval", value=1.0)
    status = conn.execute(
        "SELECT status FROM cases_raw WHERE case_id = ?", (case_id,)
    ).fetchone()[0]
    assert status == "active"


def test_single_positive_signal_does_not_promote(conn):
    case_id = write_case(conn, phase="plan", query="test")
    add_signal(conn, case_id=case_id, signal_type="merge", value=1.0)
    status = conn.execute(
        "SELECT status FROM cases_raw WHERE case_id = ?", (case_id,)
    ).fetchone()[0]
    assert status == "quarantine"


def test_composite_reward_for_case_after_signals(conn):
    case_id = write_case(conn, phase="plan", query="test")
    add_signal(conn, case_id=case_id, signal_type="merge", value=1.0)
    reward = composite_reward_for_case(conn, case_id)
    assert reward == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Prune / promote / update / delete / link
# ---------------------------------------------------------------------------


def test_prune_dry_run_does_not_archive(conn):
    case_id = write_case(conn, phase="plan", query="test")
    # Backdate it
    conn.execute(
        "UPDATE cases_raw SET created = ?, reward = 0.1 WHERE case_id = ?",
        (now() - (100 * 86400), case_id),
    )
    candidates = prune(conn, dry_run=True, reward_below=0.3, older_than_days=90)
    assert case_id in candidates
    status = conn.execute(
        "SELECT status FROM cases_raw WHERE case_id = ?", (case_id,)
    ).fetchone()[0]
    assert status == "quarantine"  # not archived


def test_prune_confirmed_archives(conn):
    case_id = write_case(conn, phase="plan", query="test")
    conn.execute(
        "UPDATE cases_raw SET created = ?, reward = 0.1 WHERE case_id = ?",
        (now() - (100 * 86400), case_id),
    )
    prune(conn, dry_run=False, reward_below=0.3, older_than_days=90)
    status = conn.execute(
        "SELECT status FROM cases_raw WHERE case_id = ?", (case_id,)
    ).fetchone()[0]
    assert status == "archived"


def test_promote_sets_status(conn):
    case_id = write_case(conn, phase="plan", query="test")
    promote(conn, case_id)
    status = conn.execute(
        "SELECT status FROM cases_raw WHERE case_id = ?", (case_id,)
    ).fetchone()[0]
    assert status == "promoted"


def test_update_case_title(conn):
    case_id = write_case(conn, phase="plan", query="test", title="old")
    update_case(conn, case_id, title="new")
    title = conn.execute(
        "SELECT title FROM cases_raw WHERE case_id = ?", (case_id,)
    ).fetchone()[0]
    assert title == "new"


def test_delete_case_cascades(conn):
    case_id = write_case(conn, phase="plan", query="test")
    add_signal(conn, case_id=case_id, signal_type="merge", value=1.0)

    delete_case(conn, case_id)

    assert (
        conn.execute(
            "SELECT COUNT(*) FROM cases_raw WHERE case_id = ?", (case_id,)
        ).fetchone()[0]
        == 0
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM signals WHERE case_id = ?", (case_id,)
        ).fetchone()[0]
        == 0
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM cases_vec WHERE case_id = ?", (case_id,)
        ).fetchone()[0]
        == 0
    )


def test_link_cases_canonical_order(conn):
    a = write_case(conn, phase="plan", query="a")
    b = write_case(conn, phase="plan", query="b")
    link_cases(conn, b, a)  # reversed order
    row = conn.execute(
        "SELECT case_id_a, case_id_b FROM case_links WHERE case_id_a = ? AND case_id_b = ?",
        (min(a, b), max(a, b)),
    ).fetchone()
    assert row is not None


def test_link_cases_rejects_self(conn):
    case_id = write_case(conn, phase="plan", query="test")
    with pytest.raises(ValueError):
        link_cases(conn, case_id, case_id)
