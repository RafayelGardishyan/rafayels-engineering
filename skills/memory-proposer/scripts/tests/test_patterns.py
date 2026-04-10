"""Tests for patterns.py: cluster detection + centroid matching."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("scipy", reason="scipy required for patterns.py")

from patterns import (
    CENTROID_MATCH_THRESHOLD,
    CLUSTER_THRESHOLD,
    Cluster,
    detect_clusters,
    match_to_existing_pattern,
    persist_cluster,
    summarize_cluster,
)


def test_detect_clusters_empty_bank(conn):
    assert detect_clusters(conn) == []


def test_detect_clusters_below_minimum(conn):
    """Fewer than 5 cases returns no clusters."""
    from capture import add_signal, write_case

    for i in range(3):
        cid = write_case(conn, phase="plan", query=f"test {i}")
        add_signal(conn, case_id=cid, signal_type="merge", value=1.0)
        add_signal(conn, case_id=cid, signal_type="approval", value=1.0)
    clusters = detect_clusters(conn, min_cluster_size=5)
    assert clusters == []


def test_persist_and_match_cluster(conn):
    """Persist a cluster, then match a new centroid to it."""
    centroid = np.random.default_rng(1).random(384, dtype=np.float32)
    centroid /= np.linalg.norm(centroid)

    cluster = Cluster(case_ids=[1, 2, 3], centroid=centroid, avg_reward=0.8)
    pattern_id = persist_cluster(conn, cluster, summary="test pattern")
    assert pattern_id > 0

    # Exact same centroid should match
    matched = match_to_existing_pattern(conn, centroid)
    assert matched == pattern_id


def test_match_different_centroid_returns_none(conn):
    """Very different centroids don't match."""
    centroid_a = np.random.default_rng(1).random(384, dtype=np.float32)
    centroid_a /= np.linalg.norm(centroid_a)
    centroid_b = np.random.default_rng(999).random(384, dtype=np.float32)
    centroid_b /= np.linalg.norm(centroid_b)

    cluster = Cluster(case_ids=[1, 2, 3], centroid=centroid_a, avg_reward=0.8)
    persist_cluster(conn, cluster)

    matched = match_to_existing_pattern(conn, centroid_b)
    assert matched is None


def test_summarize_cluster_returns_description(conn):
    from capture import add_signal, write_case

    ids = []
    for i in range(3):
        cid = write_case(conn, phase="plan", query=f"similar test {i}", title=f"case {i}")
        add_signal(conn, case_id=cid, signal_type="merge", value=1.0)
        add_signal(conn, case_id=cid, signal_type="approval", value=1.0)
        ids.append(cid)

    centroid = np.ones(384, dtype=np.float32)
    centroid /= np.linalg.norm(centroid)
    cluster = Cluster(case_ids=ids, centroid=centroid, avg_reward=0.9)

    summary = summarize_cluster(conn, cluster)
    assert "plan" in summary
    assert "3 cases" in summary
