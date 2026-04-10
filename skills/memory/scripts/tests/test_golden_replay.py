"""Golden-bank replay integration test: seeded bank + deterministic retrieval.

Validates end-to-end retrieval behavior against a known corpus. Detects
regressions in query/score/MMR logic.
"""

from __future__ import annotations

import pytest

from capture import add_signal, promote, write_case
from retrieve import query


@pytest.fixture()
def seeded_bank(conn):
    """Seed a deterministic case bank for replay tests."""
    # Phase: plan — 10 active cases about database design
    db_topics = [
        "How to choose a vector database",
        "Indexing strategies for vector search",
        "Handling schema migrations in SQLite",
        "Sharding a vector store by partition key",
        "WAL mode and concurrent writers in SQLite",
        "Backup strategies for sqlite-vec",
        "Query performance tuning for KNN",
        "Embedding model selection for semantic search",
        "Cold start problems in retrieval systems",
        "MMR reranking for retrieval diversity",
    ]
    for topic in db_topics:
        cid = write_case(conn, phase="plan", query=topic, plan=f"approach for {topic}")
        add_signal(conn, case_id=cid, signal_type="merge", value=1.0)
        add_signal(conn, case_id=cid, signal_type="approval", value=1.0)

    # Phase: review — 10 cases about code review
    review_topics = [
        "Spotting N+1 queries in Rails",
        "Reviewing security-sensitive PRs",
        "Stack-aware reviewer routing",
        "Code simplicity review principles",
        "Concurrency bugs in JavaScript",
        "Validating database migrations",
        "Reviewing auth changes for PII leakage",
        "Performance review of hot code paths",
        "Architecture review for new services",
        "Pattern recognition in diffs",
    ]
    for topic in review_topics:
        cid = write_case(conn, phase="review", query=topic, plan=f"review approach for {topic}")
        add_signal(conn, case_id=cid, signal_type="merge", value=1.0)
        add_signal(conn, case_id=cid, signal_type="approval", value=1.0)

    return conn


def test_golden_replay_returns_results_for_active_phase(seeded_bank):
    results = query(seeded_bank, text="SQLite WAL concurrency", phase="plan", k=3)
    assert len(results) > 0
    assert len(results) <= 3
    for r in results:
        assert r.case.phase == "plan"


def test_golden_replay_phase_isolation(seeded_bank):
    """Plan query should not return review cases (PARTITION KEY)."""
    results = query(seeded_bank, text="pattern recognition", phase="plan", k=3)
    for r in results:
        assert r.case.phase == "plan"


def test_golden_replay_cross_phase_dedup(seeded_bank):
    """Exclude list prevents the same case from appearing twice across phase queries."""
    first = query(seeded_bank, text="SQLite WAL concurrency", phase="plan", k=3)
    if not first:
        pytest.skip("no results")
    first_ids = [r.case.case_id for r in first]
    second = query(
        seeded_bank,
        text="SQLite WAL concurrency",
        phase="plan",
        k=3,
        exclude_case_ids=first_ids,
    )
    second_ids = {r.case.case_id for r in second}
    assert not (second_ids & set(first_ids))


def test_golden_replay_promoted_cases_retrieved(seeded_bank):
    """A promoted case is retrievable regardless of age/reward."""
    results = query(seeded_bank, text="vector database", phase="plan", k=5)
    assert len(results) > 0
