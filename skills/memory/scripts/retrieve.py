"""Retrieve: semantic query over the case bank with MMR diversity,
cold-start handling, retrieval cap, and exponential reward decay.

Pipeline:
    1. should_retrieve() — skip if bank has fewer than K*3 active cases per phase
    2. embed query text (cached per workflow_run_id where possible)
    3. sqlite-vec KNN with top-10 candidates
    4. Apply retrieval cap penalty (demote over-retrieved cases)
    5. Apply reward decay (exp(-age_days/60))
    6. MMR rerank with λ=0.5 to K=3 final results
    7. Log retrievals for cap tracking
    8. Format as LLM-ready markdown

All functions take `conn: sqlite3.Connection` explicitly.
"""

from __future__ import annotations

import json
import math
import sqlite3
import time
from dataclasses import dataclass

import numpy as np

from db import Case, SqliteVecIndex, now
from embedder import EmbedderUnavailable, embed

DEFAULT_K = 3
CANDIDATE_POOL_SIZE = 10  # top-N from sqlite-vec, reranked to K by MMR
DEFAULT_LAMBDA = 0.5
DECAY_TAU_DAYS = 60.0
RETRIEVAL_CAP_RATIO = 0.30  # max 30% of recent retrievals per case
RETRIEVAL_CAP_LOOKBACK_DAYS = 7
MIN_RETRIEVAL_SAMPLE = 10  # need this many recent retrievals before cap kicks in


@dataclass(frozen=True)
class RetrievedCase:
    case: Case
    distance: float
    decayed_reward: float
    cap_penalty: float
    final_score: float
    rank: int


# ---------------------------------------------------------------------------
# Cold-start check
# ---------------------------------------------------------------------------


def should_retrieve(
    conn: sqlite3.Connection, phase: str, k: int = DEFAULT_K
) -> bool:
    """Return False if the per-phase bank has fewer than k*3 active cases.

    Prevents noisy retrieval from a near-empty bank during bootstrap.
    """
    count = conn.execute(
        "SELECT COUNT(*) FROM cases_raw WHERE phase = ? AND status IN ('active','promoted')",
        (phase,),
    ).fetchone()[0]
    return count >= k * 3


# ---------------------------------------------------------------------------
# Reward decay
# ---------------------------------------------------------------------------


def apply_decay(reward: float, age_days: float, tau: float = DECAY_TAU_DAYS) -> float:
    """Exponential decay: reward * exp(-age_days/tau).

    tau=60 days gives a ~42-day half-life. Promoted cases skip decay.
    """
    return reward * math.exp(-age_days / tau)


# ---------------------------------------------------------------------------
# Retrieval cap penalty
# ---------------------------------------------------------------------------


def retrieval_cap_penalty(
    conn: sqlite3.Connection,
    case_id: int,
    *,
    lookback_days: int = RETRIEVAL_CAP_LOOKBACK_DAYS,
    cap_ratio: float = RETRIEVAL_CAP_RATIO,
) -> float:
    """Return a penalty in [0, 1] for over-retrieved cases.

    0 = no penalty (case under cap).
    Penalty scales linearly once the case's share of recent retrievals exceeds cap_ratio.

    If there are fewer than MIN_RETRIEVAL_SAMPLE recent retrievals, returns 0 (not enough data).
    """
    since = now() - (lookback_days * 86400)
    total = conn.execute(
        "SELECT COUNT(*) FROM retrievals WHERE created >= ?", (since,)
    ).fetchone()[0]
    if total < MIN_RETRIEVAL_SAMPLE:
        return 0.0
    this_case = conn.execute(
        "SELECT COUNT(*) FROM retrievals WHERE case_id = ? AND created >= ?",
        (case_id, since),
    ).fetchone()[0]
    ratio = this_case / total
    if ratio <= cap_ratio:
        return 0.0
    # Over cap: scale penalty up to 1.0 at ratio == 1.0
    excess = ratio - cap_ratio
    max_excess = 1.0 - cap_ratio
    return min(1.0, excess / max_excess)


# ---------------------------------------------------------------------------
# MMR rerank
# ---------------------------------------------------------------------------


def _load_embedding(conn: sqlite3.Connection, case_id: int) -> np.ndarray | None:
    """Fetch a case's raw embedding from cases_vec for MMR similarity computation."""
    import struct

    row = conn.execute(
        "SELECT embedding FROM cases_vec WHERE case_id = ?", (case_id,)
    ).fetchone()
    if row is None or row[0] is None:
        return None
    raw = row[0]
    count = len(raw) // 4
    values = struct.unpack(f"{count}f", raw)
    return np.asarray(values, dtype=np.float32)


def mmr_rerank(
    query_vec: np.ndarray,
    candidates: list[tuple[int, np.ndarray, float, float]],
    k: int = DEFAULT_K,
    lambda_: float = DEFAULT_LAMBDA,
) -> list[tuple[int, np.ndarray, float, float]]:
    """Maximal Marginal Relevance reranking.

    candidates: list of (case_id, embedding, distance, final_score_before_mmr)
    Returns up to k candidates balancing relevance (final_score) against
    diversity (dissimilarity from already-selected items).

    Uses the pre-computed `final_score_before_mmr` as the relevance signal,
    not raw distance, so reward/decay/cap penalties influence selection.
    """
    if len(candidates) <= k:
        return list(candidates)

    # L2-normalize embeddings for cosine similarity
    def norm(v: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    normed_q = norm(query_vec)
    normed = [(cid, norm(emb), dist, score) for cid, emb, dist, score in candidates]

    selected: list[tuple[int, np.ndarray, float, float]] = []
    remaining = list(normed)

    while len(selected) < k and remaining:
        best_idx = 0
        best_mmr = -float("inf")
        for i, (cid, emb, dist, score) in enumerate(remaining):
            relevance = score  # pre-computed score (higher = better)
            if selected:
                max_sim = max(float(np.dot(emb, s[1])) for s in selected)
            else:
                max_sim = 0.0
            mmr_score = lambda_ * relevance - (1 - lambda_) * max_sim
            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_idx = i
        selected.append(remaining.pop(best_idx))

    return selected


# ---------------------------------------------------------------------------
# Main query
# ---------------------------------------------------------------------------


def query(
    conn: sqlite3.Connection,
    *,
    text: str,
    phase: str,
    k: int = DEFAULT_K,
    workflow_run_id: str | None = None,
    exclude_case_ids: list[int] | None = None,
    include_quarantine: bool = False,
) -> list[RetrievedCase]:
    """Query the case bank for the top-k cases relevant to `text`.

    Returns empty list if cold-start threshold not met or embedder unavailable.

    Pipeline: sqlite-vec top-10 → score → MMR rerank → top-k → log.
    """
    exclude = set(exclude_case_ids or [])

    if not should_retrieve(conn, phase, k):
        return []

    # Embed the query
    try:
        query_vecs = embed([text])
    except EmbedderUnavailable:
        return []
    if not query_vecs:
        return []
    query_vec = query_vecs[0]

    # sqlite-vec KNN with phase partition pre-filter
    vec_index = SqliteVecIndex(conn)
    raw_hits = vec_index.search(query_vec, phase=phase, k=CANDIDATE_POOL_SIZE + len(exclude))
    if not raw_hits:
        return []

    # Hydrate candidates with metadata + apply scoring
    scored: list[tuple[int, np.ndarray, float, float, Case, float, float]] = []
    current_time = now()
    for case_id, distance in raw_hits:
        if case_id in exclude:
            continue

        row = conn.execute(
            "SELECT * FROM cases_raw WHERE case_id = ?", (case_id,)
        ).fetchone()
        if row is None:
            continue

        # Filter by status (default excludes quarantine)
        if not include_quarantine and row["status"] == "quarantine":
            continue
        if row["status"] == "archived":
            continue

        case = Case.from_row(row)

        # Apply reward decay (promoted cases skip decay)
        age_days = (current_time - case.created) / 86400.0
        if case.status == "promoted":
            decayed = case.reward
        else:
            decayed = apply_decay(case.reward, age_days)

        # Apply retrieval cap penalty
        penalty = retrieval_cap_penalty(conn, case_id)

        # Combine distance, decayed reward, and cap penalty into a final score
        # score in [0, ~2]: similarity (1-dist) weighted by decayed reward, minus penalty
        similarity = 1.0 - distance
        score = (similarity * (0.5 + decayed)) * (1.0 - penalty)

        emb = _load_embedding(conn, case_id)
        if emb is None:
            continue

        scored.append((case_id, emb, distance, score, case, decayed, penalty))

        if len(scored) >= CANDIDATE_POOL_SIZE:
            break

    if not scored:
        return []

    # MMR rerank the top candidates
    mmr_input = [(cid, emb, dist, score) for cid, emb, dist, score, _, _, _ in scored]
    reranked = mmr_rerank(query_vec, mmr_input, k=k, lambda_=DEFAULT_LAMBDA)

    # Build final RetrievedCase list with rank
    case_lookup = {cid: (case, decayed, penalty) for cid, _, _, _, case, decayed, penalty in scored}
    final: list[RetrievedCase] = []
    for rank, (case_id, _emb, distance, score) in enumerate(reranked, start=1):
        case, decayed, penalty = case_lookup[case_id]
        final.append(
            RetrievedCase(
                case=case,
                distance=distance,
                decayed_reward=decayed,
                cap_penalty=penalty,
                final_score=score,
                rank=rank,
            )
        )

    # Log retrievals for cap tracking
    _log_retrievals(conn, final, phase=phase, workflow_run_id=workflow_run_id)

    return final


def _log_retrievals(
    conn: sqlite3.Connection,
    results: list[RetrievedCase],
    *,
    phase: str,
    workflow_run_id: str | None,
) -> None:
    """Append entries to the retrievals audit table."""
    if not results:
        return
    from db import write_transaction

    timestamp = now()
    with write_transaction(conn):
        conn.executemany(
            """
            INSERT INTO retrievals (case_id, phase, workflow_run_id, distance, rank, created)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (r.case.case_id, phase, workflow_run_id, r.distance, r.rank, timestamp)
                for r in results
            ],
        )


# ---------------------------------------------------------------------------
# Format for LLM context injection
# ---------------------------------------------------------------------------


def format_for_injection(
    results: list[RetrievedCase], *, include_negatives: bool = True
) -> str:
    """Render retrieved cases as LLM-ready markdown.

    Positives (reward > 0.5) and negatives (reward <= 0.5) are rendered in
    separate sections with different framing: positives as "imitate",
    negatives as short "avoid" anti-patterns.
    """
    if not results:
        return ""

    positives = [r for r in results if r.case.reward > 0.5]
    negatives = [r for r in results if r.case.reward <= 0.5]

    lines: list[str] = ["## Relevant Cases from Memory"]

    if positives:
        lines.append("\n### Past Successes (imitate the approach)")
        for r in positives:
            lines.append(
                f"- **Case #{r.case.case_id}** "
                f"[reward={r.case.reward:.2f}, status={r.case.status}]"
            )
            if r.case.injection_summary:
                for line in r.case.injection_summary.splitlines():
                    lines.append(f"  {line}")

    if negatives and include_negatives:
        lines.append("\n### Past Failures (avoid these mistakes)")
        for r in negatives:
            lines.append(
                f"- **Case #{r.case.case_id}** "
                f"[reward={r.case.reward:.2f}]: "
                f"{r.case.title or r.case.query[:100]}"
            )
            if r.case.outcome:
                lines.append(f"  → Why it failed: {r.case.outcome[:200]}")

    return "\n".join(lines)


def results_to_json(results: list[RetrievedCase]) -> list[dict]:
    """Return a JSON-serializable list of retrieved cases."""
    return [
        {
            "case_id": r.case.case_id,
            "phase": r.case.phase,
            "status": r.case.status,
            "reward": r.case.reward,
            "decayed_reward": r.decayed_reward,
            "distance": r.distance,
            "cap_penalty": r.cap_penalty,
            "final_score": r.final_score,
            "rank": r.rank,
            "title": r.case.title,
            "query": r.case.query,
            "plan": r.case.plan,
            "outcome": r.case.outcome,
            "injection_summary": r.case.injection_summary,
            "tags": r.case.tags,
        }
        for r in results
    ]
