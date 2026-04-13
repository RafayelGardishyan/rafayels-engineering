"""Capture: write cases, append signals, compute rewards, prune, promote.

Key design decisions:
- `composite_reward(signals)` is a PURE FUNCTION taking a list of (type, value) tuples.
  Easy to unit-test with synthetic data. The DB-fetching wrapper is separate.
- Quarantine-on-write: new cases start in status='quarantine'. Promoted to 'active'
  when they accumulate 2+ positive signals (enforced by SQL trigger in 001_initial.sql).
- All write paths use `write_transaction()` to acquire the writer lock via BEGIN IMMEDIATE.
- Dependency injection: every function takes `conn` explicitly.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import numpy as np

from db import Case, SqliteVecIndex, detect_project, now, write_transaction
from embedder import EmbedderUnavailable, embed

# ---------------------------------------------------------------------------
# Composite reward — pure function
# ---------------------------------------------------------------------------

SIGNAL_WEIGHTS: dict[str, float] = {
    "merge": 0.40,
    "approval": 0.30,
    "review": 0.20,
    "regression": 0.10,
}

NEUTRAL_REWARD = 0.5


def composite_reward(signals: list[tuple[str, float]]) -> float:
    """Weighted mean of signal values, mapped from [-1,1] to [0,1].

    Pure function — takes a list of (signal_type, value) tuples.
    No DB dependency. Unit-testable with synthetic data.

    Returns NEUTRAL_REWARD (0.5) for empty signal lists.
    """
    if not signals:
        return NEUTRAL_REWARD

    by_type: dict[str, list[float]] = defaultdict(list)
    for sig_type, value in signals:
        if sig_type in SIGNAL_WEIGHTS:
            by_type[sig_type].append(value)

    if not by_type:
        return NEUTRAL_REWARD

    numerator = 0.0
    denominator = 0.0
    for sig_type, values in by_type.items():
        weight = SIGNAL_WEIGHTS[sig_type]
        avg = sum(values) / len(values)
        numerator += weight * avg
        denominator += weight

    if denominator == 0.0:
        return NEUTRAL_REWARD

    normalized = numerator / denominator  # still in [-1,1]
    mapped = (normalized + 1.0) / 2.0  # -> [0,1]
    return max(0.0, min(1.0, mapped))


def composite_reward_for_case(conn: sqlite3.Connection, case_id: int) -> float:
    """Fetch signals for a case and compute composite reward.

    Thin wrapper around the pure `composite_reward()` function.
    """
    rows = conn.execute(
        "SELECT signal_type, value FROM signals WHERE case_id = ?", (case_id,)
    ).fetchall()
    return composite_reward([(row["signal_type"], row["value"]) for row in rows])


# ---------------------------------------------------------------------------
# Token cap for injection_summary
# ---------------------------------------------------------------------------


def enforce_token_cap(text: str, max_tokens: int = 300) -> str:
    """Truncate text to max_tokens, preferring sentence boundaries.

    Uses tiktoken if available (accurate), else word-count fallback (~1.3 tokens/word).
    """
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        tokens = enc.encode(text)
        if len(tokens) <= max_tokens:
            return text
        truncated = enc.decode(tokens[:max_tokens])
        for punct in [". ", "! ", "? ", "\n\n"]:
            idx = truncated.rfind(punct)
            if idx > len(truncated) * 0.7:
                return truncated[: idx + len(punct)].rstrip()
        return truncated.rstrip() + "…"
    except ImportError:
        words = text.split()
        max_words = int(max_tokens / 1.3)
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + "…"


def _build_injection_summary(
    *, title: str | None, query: str, plan: str | None, outcome: str | None
) -> str:
    """Build a compact ~300-token summary for LLM injection."""
    parts: list[str] = []
    if title:
        parts.append(f"**{title}**")
    if query:
        parts.append(f"Query: {query}")
    if plan:
        parts.append(f"Approach: {plan}")
    if outcome:
        parts.append(f"Outcome: {outcome}")
    text = "\n".join(parts)
    return enforce_token_cap(text, max_tokens=300)


def _build_embedding_text(query: str, plan: str | None) -> str:
    """Text used to generate the case embedding. Query + plan joined."""
    if plan:
        return f"{query}\n\n{plan}"
    return query


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


def write_case(
    conn: sqlite3.Connection,
    *,
    phase: str,
    query: str,
    case_type: str | None = None,
    title: str | None = None,
    plan: str | None = None,
    trajectory: str | None = None,
    outcome: str | None = None,
    tags: list[str] | None = None,
    project: str | None = None,
    cwd: Path | None = None,
) -> int:
    """Write a new case to the DB. Returns the created case_id.

    The case starts in status='quarantine' and will be promoted to 'active'
    by the `promote_on_positive_signals` SQL trigger once 2+ positive signals arrive.

    Raises EmbedderUnavailable if the embedder can't be loaded — caller
    should catch this and degrade (skip write).
    """
    if phase not in {"brainstorm", "plan", "work", "review", "compound", "other"}:
        raise ValueError(f"invalid phase: {phase!r}")

    project = project or detect_project(cwd)
    tags_json = json.dumps(tags or [])
    timestamp = now()
    embedding_text = _build_embedding_text(query, plan)
    injection_summary = _build_injection_summary(
        title=title, query=query, plan=plan, outcome=outcome
    )

    # Embed BEFORE the write transaction — embedding can be slow (1s+ cold start).
    # We don't want to hold the writer lock during that.
    vecs = embed([embedding_text])
    if not vecs:
        raise EmbedderUnavailable("embed returned no vectors")
    vec = vecs[0]

    vec_index = SqliteVecIndex(conn)

    with write_transaction(conn):
        cursor = conn.execute(
            """
            INSERT INTO cases_raw (
                phase, case_type, status, reward,
                created, updated, project,
                title, query, plan, trajectory, outcome, tags, injection_summary
            ) VALUES (?, ?, 'quarantine', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                phase,
                case_type,
                NEUTRAL_REWARD,
                timestamp,
                timestamp,
                project,
                title,
                query,
                plan,
                trajectory,
                outcome,
                tags_json,
                injection_summary,
            ),
        )
        case_id = cursor.lastrowid
        assert case_id is not None
        vec_index.upsert(case_id, phase, vec)

    return case_id


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


VALID_SIGNAL_TYPES = frozenset(SIGNAL_WEIGHTS.keys())


def add_signal(
    conn: sqlite3.Connection,
    *,
    case_id: int,
    signal_type: str,
    value: float,
    source: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Append a signal to a case. The SQL trigger auto-recomputes reward and
    may promote a quarantined case to 'active'.
    """
    if signal_type not in VALID_SIGNAL_TYPES:
        raise ValueError(
            f"invalid signal_type: {signal_type!r}. "
            f"Must be one of: {sorted(VALID_SIGNAL_TYPES)}"
        )
    if not (-1.0 <= value <= 1.0):
        raise ValueError(f"signal value must be in [-1.0, 1.0], got {value}")

    metadata_json = json.dumps(metadata) if metadata else None

    with write_transaction(conn):
        conn.execute(
            """
            INSERT INTO signals (case_id, signal_type, value, source, created, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (case_id, signal_type, value, source, now(), metadata_json),
        )


# ---------------------------------------------------------------------------
# Prune / promote / update / delete
# ---------------------------------------------------------------------------


def prune(
    conn: sqlite3.Connection,
    *,
    reward_below: float = 0.3,
    older_than_days: int = 90,
    dry_run: bool = True,
) -> list[int]:
    """Archive cases with reward below threshold and age > N days.

    Cases with status='promoted' are exempt.
    In dry_run mode, returns the case_ids that WOULD be archived without changing them.
    Otherwise archives (status='archived') and returns the list of archived ids.
    """
    cutoff = now() - (older_than_days * 86400)
    candidates = conn.execute(
        """
        SELECT case_id FROM cases_raw
        WHERE reward < ?
          AND created < ?
          AND status IN ('active', 'quarantine')
        """,
        (reward_below, cutoff),
    ).fetchall()
    case_ids = [row["case_id"] for row in candidates]

    if dry_run or not case_ids:
        return case_ids

    with write_transaction(conn):
        placeholders = ",".join("?" * len(case_ids))
        conn.execute(
            f"UPDATE cases_raw SET status = 'archived', updated = ? "
            f"WHERE case_id IN ({placeholders})",
            (now(), *case_ids),
        )
    return case_ids


def promote(conn: sqlite3.Connection, case_id: int) -> None:
    """Pin a case as 'promoted' — never auto-archived, surfaced in retrieval."""
    with write_transaction(conn):
        conn.execute(
            "UPDATE cases_raw SET status = 'promoted', updated = ? WHERE case_id = ?",
            (now(), case_id),
        )


def update_case(
    conn: sqlite3.Connection,
    case_id: int,
    *,
    title: str | None = None,
    tags: list[str] | None = None,
    outcome: str | None = None,
) -> None:
    """Update mutable fields on a case. Does NOT re-embed (use write a new case for that)."""
    updates: list[str] = []
    params: list = []
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(tags))
    if outcome is not None:
        updates.append("outcome = ?")
        params.append(outcome)
    if not updates:
        return
    updates.append("updated = ?")
    params.append(now())
    params.append(case_id)
    with write_transaction(conn):
        conn.execute(
            f"UPDATE cases_raw SET {', '.join(updates)} WHERE case_id = ?",
            tuple(params),
        )


def delete_case(conn: sqlite3.Connection, case_id: int) -> None:
    """Hard-delete a case. Cascades to signals, retrievals, case_links, and cases_vec.

    FK CASCADE handles the plain tables. cases_vec is deleted separately because
    it's a virtual table not bound by the FK.
    """
    vec_index = SqliteVecIndex(conn)
    with write_transaction(conn):
        vec_index.delete(case_id)
        conn.execute("DELETE FROM cases_raw WHERE case_id = ?", (case_id,))


def link_cases(
    conn: sqlite3.Connection,
    case_id_a: int,
    case_id_b: int,
    link_type: str = "related",
) -> None:
    """Mark two cases as related. Canonical order enforced (a < b)."""
    if case_id_a == case_id_b:
        raise ValueError("cannot link a case to itself")
    lo, hi = sorted([case_id_a, case_id_b])
    with write_transaction(conn):
        conn.execute(
            """
            INSERT OR IGNORE INTO case_links (case_id_a, case_id_b, link_type, created)
            VALUES (?, ?, ?, ?)
            """,
            (lo, hi, link_type, now()),
        )
