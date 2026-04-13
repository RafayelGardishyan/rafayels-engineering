"""Pattern detection: cluster successful cases, find emerging patterns.

Uses agglomerative clustering (UPGMA) on case embeddings via scipy.
Threshold 0.15 tuned for BGE-small compressed cosine distances.

Persists clusters as centroids (not IDs) so cluster identity is stable
across re-clustering runs — new cluster is matched to existing pattern
by centroid cosine similarity (threshold 0.10).
"""

from __future__ import annotations

import json
import sqlite3
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# Add memory skill scripts to path so we can reuse its modules
MEMORY_SCRIPTS = (
    Path(__file__).resolve().parent.parent.parent / "memory" / "scripts"
)
sys.path.insert(0, str(MEMORY_SCRIPTS))

from db import now  # noqa: E402

CLUSTER_THRESHOLD = 0.15  # BGE-small cosine distance for pattern clusters
CENTROID_MATCH_THRESHOLD = 0.10  # match new cluster to existing pattern
DEFAULT_MIN_CLUSTER_SIZE = 5
DEFAULT_MIN_REWARD = 0.6


@dataclass(frozen=True)
class Cluster:
    case_ids: list[int]
    centroid: np.ndarray
    avg_reward: float


def _load_embedding_bytes(raw: bytes) -> np.ndarray:
    count = len(raw) // 4
    return np.asarray(struct.unpack(f"{count}f", raw), dtype=np.float32)


def _pack_centroid(vec: np.ndarray) -> bytes:
    v = vec.astype(np.float32)
    return struct.pack(f"{len(v)}f", *v)


def _fetch_active_embeddings(
    conn: sqlite3.Connection, min_reward: float
) -> tuple[list[int], list[float], np.ndarray]:
    """Return (case_ids, rewards, embeddings_matrix) for active+promoted cases above min_reward."""
    rows = conn.execute(
        """
        SELECT cr.case_id, cr.reward, cv.embedding
        FROM cases_raw cr
        JOIN cases_vec cv USING (case_id)
        WHERE cr.status IN ('active', 'promoted')
          AND cr.reward >= ?
        """,
        (min_reward,),
    ).fetchall()
    if not rows:
        return [], [], np.empty((0, 384), dtype=np.float32)
    case_ids = [r["case_id"] for r in rows]
    rewards = [r["reward"] for r in rows]
    embeddings = np.vstack(
        [_load_embedding_bytes(r["embedding"]) for r in rows]
    )
    # L2-normalize so cosine distance == 1 - dot
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    embeddings = embeddings / norms
    return case_ids, rewards, embeddings


def _agglomerative_clusters(
    embeddings: np.ndarray, threshold: float
) -> np.ndarray:
    """Cluster L2-normalized embeddings by cosine distance using scipy UPGMA.

    Returns an array of cluster labels.
    """
    try:
        from scipy.cluster.hierarchy import fcluster, linkage
        from scipy.spatial.distance import pdist
    except ImportError as exc:
        raise RuntimeError(
            "scipy not installed — memory-proposer requires scipy. "
            "Run: pip install -r skills/memory-proposer/scripts/requirements.txt"
        ) from exc

    if len(embeddings) < 2:
        return np.array([1] * len(embeddings), dtype=int)

    dists = pdist(embeddings, metric="cosine")
    # method='average' = UPGMA, correct for cosine; ward would require Euclidean
    Z = linkage(dists, method="average")
    return fcluster(Z, t=threshold, criterion="distance")


def detect_clusters(
    conn: sqlite3.Connection,
    *,
    min_cluster_size: int | None = None,
    min_reward: float = DEFAULT_MIN_REWARD,
    threshold: float = CLUSTER_THRESHOLD,
) -> list[Cluster]:
    """Detect pattern clusters in the case bank.

    Returns a list of clusters above the minimum size, with centroids.
    """
    case_ids, rewards, embeddings = _fetch_active_embeddings(conn, min_reward)
    n = len(case_ids)
    if n < 5:
        return []

    labels = _agglomerative_clusters(embeddings, threshold)

    if min_cluster_size is None:
        min_cluster_size = max(DEFAULT_MIN_CLUSTER_SIZE, int(0.01 * n))

    clusters: list[Cluster] = []
    for label in np.unique(labels):
        members = np.where(labels == label)[0]
        if len(members) < min_cluster_size:
            continue
        member_ids = [case_ids[i] for i in members]
        member_rewards = [rewards[i] for i in members]
        centroid = embeddings[members].mean(axis=0)
        cn = np.linalg.norm(centroid)
        if cn > 0:
            centroid = centroid / cn
        clusters.append(
            Cluster(
                case_ids=member_ids,
                centroid=centroid,
                avg_reward=float(np.mean(member_rewards)),
            )
        )
    return clusters


def match_to_existing_pattern(
    conn: sqlite3.Connection,
    new_centroid: np.ndarray,
    *,
    match_threshold: float = CENTROID_MATCH_THRESHOLD,
) -> int | None:
    """Check if a new cluster matches an existing pattern in the DB.

    Returns the existing pattern_id if found, None otherwise.
    This enables pattern identity stability across re-clustering runs.
    """
    rows = conn.execute(
        "SELECT pattern_id, centroid FROM patterns WHERE status != 'ignored'"
    ).fetchall()
    for row in rows:
        existing = _load_embedding_bytes(row["centroid"])
        en = np.linalg.norm(existing)
        if en > 0:
            existing = existing / en
        distance = 1.0 - float(np.dot(new_centroid, existing))
        if distance <= match_threshold:
            return row["pattern_id"]
    return None


def persist_cluster(
    conn: sqlite3.Connection,
    cluster: Cluster,
    *,
    summary: str | None = None,
) -> int:
    """Persist or update a pattern in the `patterns` table.

    If the cluster matches an existing pattern (centroid similarity),
    updates that pattern. Otherwise creates a new one.
    Returns the pattern_id.
    """
    existing_id = match_to_existing_pattern(conn, cluster.centroid)
    timestamp = now()
    centroid_blob = _pack_centroid(cluster.centroid)
    case_ids_json = json.dumps(cluster.case_ids)

    conn.execute("BEGIN IMMEDIATE")
    try:
        if existing_id is not None:
            conn.execute(
                """
                UPDATE patterns
                SET case_ids = ?, case_count = ?, avg_reward = ?,
                    centroid = ?, updated = ?
                WHERE pattern_id = ?
                """,
                (
                    case_ids_json,
                    len(cluster.case_ids),
                    cluster.avg_reward,
                    centroid_blob,
                    timestamp,
                    existing_id,
                ),
            )
            pattern_id = existing_id
        else:
            cursor = conn.execute(
                """
                INSERT INTO patterns (
                    centroid, case_ids, case_count, avg_reward,
                    summary, status, created, updated
                ) VALUES (?, ?, ?, ?, ?, 'detected', ?, ?)
                """,
                (
                    centroid_blob,
                    case_ids_json,
                    len(cluster.case_ids),
                    cluster.avg_reward,
                    summary,
                    timestamp,
                    timestamp,
                ),
            )
            pattern_id = cursor.lastrowid  # type: ignore[assignment]
        conn.execute("COMMIT")
    except sqlite3.OperationalError:
        conn.execute("ROLLBACK")
        raise

    return pattern_id


def summarize_cluster(conn: sqlite3.Connection, cluster: Cluster) -> str:
    """Generate a human-readable summary of a cluster from its member cases.

    Lightweight approach: return the most common phase + reward + top member titles.
    """
    if not cluster.case_ids:
        return ""
    placeholders = ",".join("?" * len(cluster.case_ids))
    rows = conn.execute(
        f"SELECT phase, title, outcome FROM cases_raw WHERE case_id IN ({placeholders})",
        cluster.case_ids,
    ).fetchall()

    phase_counts: dict[str, int] = {}
    titles: list[str] = []
    for row in rows:
        phase = row["phase"]
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
        if row["title"]:
            titles.append(row["title"])

    top_phase = max(phase_counts, key=phase_counts.get) if phase_counts else "unknown"
    title_sample = titles[:3]

    return (
        f"Recurring {top_phase} pattern across {len(cluster.case_ids)} cases "
        f"(avg reward {cluster.avg_reward:.2f}). "
        f"Sample titles: {'; '.join(title_sample)}"
    )
