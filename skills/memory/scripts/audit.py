"""Audit: report, doctor, read, list, export, import.

Read-side operations and self-diagnostics. Writes are in capture.py.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from db import Case, Config, now, user_scope_db_path
from embedder import daemon_socket_path, model_cache_dir, ping_daemon


# ---------------------------------------------------------------------------
# Read / list
# ---------------------------------------------------------------------------


def read_case(conn: sqlite3.Connection, case_id: int) -> Case | None:
    row = conn.execute("SELECT * FROM cases_raw WHERE case_id = ?", (case_id,)).fetchone()
    if row is None:
        return None
    return Case.from_row(row)


def list_cases(
    conn: sqlite3.Connection,
    *,
    phase: str | None = None,
    status: str | None = None,
    project: str | None = None,
    tag: str | None = None,
    limit: int = 50,
) -> list[Case]:
    """List cases filtered by optional metadata columns."""
    clauses: list[str] = []
    params: list[Any] = []
    if phase:
        clauses.append("phase = ?")
        params.append(phase)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if project:
        clauses.append("project = ?")
        params.append(project)
    if tag:
        # tags is stored as a JSON array — do a text match
        clauses.append("tags LIKE ?")
        params.append(f'%"{tag}"%')
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM cases_raw {where} ORDER BY created DESC LIMIT ?",
        tuple(params),
    ).fetchall()
    return [Case.from_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def report_stats(conn: sqlite3.Connection) -> dict:
    """Aggregate statistics: case counts, reward distribution, signal totals."""
    totals = dict(
        conn.execute(
            """
            SELECT status, COUNT(*) as c
            FROM cases_raw
            GROUP BY status
            """
        ).fetchall()
    )
    by_phase = dict(
        conn.execute(
            """
            SELECT phase, COUNT(*) as c
            FROM cases_raw
            GROUP BY phase
            """
        ).fetchall()
    )
    reward_buckets = {
        "0.0-0.2": 0,
        "0.2-0.4": 0,
        "0.4-0.6": 0,
        "0.6-0.8": 0,
        "0.8-1.0": 0,
    }
    rows = conn.execute(
        "SELECT reward FROM cases_raw WHERE status IN ('active', 'promoted')"
    ).fetchall()
    for r in rows:
        val = r[0]
        if val < 0.2:
            reward_buckets["0.0-0.2"] += 1
        elif val < 0.4:
            reward_buckets["0.2-0.4"] += 1
        elif val < 0.6:
            reward_buckets["0.4-0.6"] += 1
        elif val < 0.8:
            reward_buckets["0.6-0.8"] += 1
        else:
            reward_buckets["0.8-1.0"] += 1

    signal_counts = dict(
        conn.execute(
            """
            SELECT signal_type, COUNT(*) as c
            FROM signals
            GROUP BY signal_type
            """
        ).fetchall()
    )

    total_cases = sum(totals.values())
    total_signals = sum(signal_counts.values())

    return {
        "total_cases": total_cases,
        "total_signals": total_signals,
        "cases_by_status": totals,
        "cases_by_phase": by_phase,
        "reward_distribution": reward_buckets,
        "signals_by_type": signal_counts,
    }


def report_stale(conn: sqlite3.Connection, older_than_days: int = 90) -> list[dict]:
    """Return cases older than N days that are candidates for pruning."""
    cutoff = now() - (older_than_days * 86400)
    rows = conn.execute(
        """
        SELECT case_id, phase, reward, status, created, title
        FROM cases_raw
        WHERE created < ?
          AND status IN ('active', 'quarantine')
        ORDER BY reward ASC, created ASC
        """,
        (cutoff,),
    ).fetchall()
    return [
        {
            "case_id": r["case_id"],
            "phase": r["phase"],
            "reward": r["reward"],
            "status": r["status"],
            "age_days": int((now() - r["created"]) / 86400),
            "title": r["title"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Doctor — self-diagnosis
# ---------------------------------------------------------------------------


def doctor(conn: sqlite3.Connection | None = None) -> dict:
    """Self-diagnose memory layer readiness. Returns a JSON-serializable dict.

    Checks:
        - Python dependencies (sqlite-vec, fastembed, numpy)
        - SQLite version
        - DB file exists and is accessible
        - Schema version matches code expectations
        - Embedder daemon reachability
        - Model cache directory
    """
    checks: list[dict] = []

    # Python deps
    for pkg in ["sqlite_vec", "fastembed", "numpy"]:
        try:
            __import__(pkg)
            checks.append({"name": f"dep:{pkg}", "status": "ok"})
        except ImportError as exc:
            checks.append(
                {
                    "name": f"dep:{pkg}",
                    "status": "missing",
                    "detail": str(exc),
                    "fix": "pip install -r skills/memory/scripts/requirements.txt",
                }
            )

    # Optional dep
    try:
        __import__("tiktoken")
        checks.append({"name": "dep:tiktoken (optional)", "status": "ok"})
    except ImportError:
        checks.append(
            {
                "name": "dep:tiktoken (optional)",
                "status": "missing",
                "detail": "Token cap will use word-count fallback",
            }
        )

    # SQLite version
    checks.append(
        {
            "name": "sqlite_version",
            "status": "ok" if sqlite3.sqlite_version_info >= (3, 41, 0) else "too_old",
            "detail": sqlite3.sqlite_version,
        }
    )

    # DB file
    db_path = user_scope_db_path()
    checks.append(
        {
            "name": "db_file",
            "status": "ok" if db_path.exists() else "missing",
            "detail": str(db_path),
        }
    )

    # Schema version (if we have a connection)
    if conn is not None:
        try:
            config = Config.load(conn)
            checks.append(
                {
                    "name": "schema_version",
                    "status": "ok" if config.schema_version == 1 else "mismatch",
                    "detail": f"v{config.schema_version}",
                }
            )
            checks.append(
                {
                    "name": "embedding_model",
                    "status": "ok",
                    "detail": config.embedding_model,
                }
            )
        except (sqlite3.OperationalError, KeyError, ValueError) as exc:
            checks.append(
                {
                    "name": "schema_version",
                    "status": "error",
                    "detail": str(exc),
                }
            )

    # Embedder daemon
    checks.append(
        {
            "name": "embedder_daemon",
            "status": "running" if ping_daemon() else "not_running",
            "detail": str(daemon_socket_path()),
        }
    )

    # Model cache
    cache = model_cache_dir()
    has_model_files = cache.exists() and any(cache.iterdir())
    checks.append(
        {
            "name": "model_cache",
            "status": "warm" if has_model_files else "cold",
            "detail": str(cache),
        }
    )

    # Determine overall health
    errors = [c for c in checks if c["status"] in ("missing", "error", "too_old", "mismatch")]
    status = "healthy" if not errors else "degraded"
    if any(
        c["name"].startswith("dep:") and c["status"] == "missing" and "optional" not in c["name"]
        for c in checks
    ):
        status = "unavailable"

    return {
        "status": status,
        "checks": checks,
        "db_path": str(db_path),
    }


# ---------------------------------------------------------------------------
# Export / import
# ---------------------------------------------------------------------------


def export_jsonl(conn: sqlite3.Connection, output_path: Path | None = None) -> int:
    """Export all cases + signals as JSONL. Returns number of lines written.

    If output_path is None, writes to stdout.
    """
    lines: list[str] = []

    cases = conn.execute("SELECT * FROM cases_raw").fetchall()
    for row in cases:
        case = Case.from_row(row)
        entry = {"record": "case", **case.to_dict()}
        lines.append(json.dumps(entry))

    signals = conn.execute(
        "SELECT signal_id, case_id, signal_type, value, source, created, metadata FROM signals"
    ).fetchall()
    for row in signals:
        entry = {
            "record": "signal",
            "signal_id": row["signal_id"],
            "case_id": row["case_id"],
            "signal_type": row["signal_type"],
            "value": row["value"],
            "source": row["source"],
            "created": row["created"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }
        lines.append(json.dumps(entry))

    output = "\n".join(lines) + "\n"
    if output_path is None:
        sys.stdout.write(output)
    else:
        output_path.write_text(output)
    return len(lines)


def import_jsonl(conn: sqlite3.Connection, input_path: Path) -> dict:
    """Import cases + signals from a JSONL file. Returns counts of imported records.

    Re-embeds cases on import (uses current embedder).
    """
    from capture import add_signal, write_case

    case_count = 0
    signal_count = 0
    id_map: dict[int, int] = {}  # old case_id -> new case_id

    with input_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            record_type = entry.get("record")
            if record_type == "case":
                old_id = entry["case_id"]
                new_id = write_case(
                    conn,
                    phase=entry["phase"],
                    query=entry["query"],
                    case_type=entry.get("case_type"),
                    title=entry.get("title"),
                    plan=entry.get("plan"),
                    outcome=entry.get("outcome"),
                    tags=entry.get("tags") or [],
                    project=entry.get("project"),
                )
                id_map[old_id] = new_id
                case_count += 1
            elif record_type == "signal":
                old_case_id = entry["case_id"]
                new_case_id = id_map.get(old_case_id)
                if new_case_id is None:
                    continue
                add_signal(
                    conn,
                    case_id=new_case_id,
                    signal_type=entry["signal_type"],
                    value=entry["value"],
                    source=entry.get("source"),
                    metadata=entry.get("metadata"),
                )
                signal_count += 1

    return {"cases_imported": case_count, "signals_imported": signal_count}


# ---------------------------------------------------------------------------
# Seed from docs/solutions/
# ---------------------------------------------------------------------------


def seed_from_solutions(
    conn: sqlite3.Connection, solutions_dir: Path | None = None
) -> int:
    """Bootstrap the case bank from existing docs/solutions/ markdown files.

    Parses YAML frontmatter and creates one case per solution file.
    Cases start in status='quarantine' (default) — they need positive
    signals to become retrievable, just like any other case.
    """
    from capture import write_case

    try:
        import yaml  # type: ignore
    except ImportError:
        sys.stderr.write("[memory] pyyaml not installed — cannot seed from YAML\n")
        return 0

    solutions_dir = solutions_dir or Path("docs/solutions")
    if not solutions_dir.exists():
        return 0

    count = 0
    for md_file in solutions_dir.rglob("*.md"):
        if md_file.name in ("critical-patterns.md", "_index.md"):
            continue
        text = md_file.read_text()

        # Parse YAML frontmatter
        if not text.startswith("---\n"):
            continue
        try:
            _, frontmatter, body = text.split("---\n", 2)
            metadata = yaml.safe_load(frontmatter) or {}
        except (ValueError, yaml.YAMLError):
            continue

        title = metadata.get("title") or md_file.stem
        symptoms = metadata.get("symptoms") or []
        if isinstance(symptoms, list):
            query_text = f"{title}: {' '.join(str(s) for s in symptoms)}"
        else:
            query_text = f"{title}: {symptoms}"

        write_case(
            conn,
            phase="other",
            case_type="solution",
            title=title,
            query=query_text,
            plan=body[:2000],
            outcome=metadata.get("root_cause"),
            tags=list(metadata.get("scope") or metadata.get("tags") or []),
        )
        count += 1

    return count
