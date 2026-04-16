"""Database layer: connection, schema, migrations, typed config, dataclasses, VectorIndex protocol.

This module owns sqlite-vec integration and provides a clean abstraction
(VectorIndex protocol) so v2 can swap to lance/chroma without rewriting retrieve.py.

Design principles:
- Dependency injection: every function takes `conn: sqlite3.Connection` explicitly.
  No module-level globals.
- Specific exceptions: never bare `except Exception`.
- Typed config: `Config` dataclass loaded and validated at startup.
- Schema invariants enforced in SQL via CHECK constraints + triggers, not Python.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import struct
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np

log = logging.getLogger(__name__)

# Module-level constants
REQUIRED_SQLITE_VERSION = (3, 41, 0)
EMBEDDING_DIM = 384
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
MIGRATIONS_DIR = Path(__file__).parent / "migrations"

_FALLBACK_DB_PATH = Path.home() / ".claude" / "plugins" / "rafayels-engineering" / "memory.db"
_RESOLVER_DIR = Path(__file__).resolve().parents[2] / "project-config" / "scripts"


def user_scope_db_path() -> Path:
    """Return the user-scope DB path from project-config, with fallback.

    Resolves `memory.db_path` via the project-config resolver when available.
    Falls back to the hardcoded default if project-config is unavailable
    (missing pyyaml, missing config, malformed YAML, etc.) — the memory
    layer must stay runnable even when config is broken.
    """
    path = _FALLBACK_DB_PATH
    if str(_RESOLVER_DIR) not in sys.path:
        sys.path.insert(0, str(_RESOLVER_DIR))
    try:
        import resolver  # type: ignore[import-not-found]
    except ImportError as exc:
        log.warning("project-config unavailable (%s); using hardcoded memory DB default", exc)
    else:
        try:
            path = resolver.load_config().memory_db_path
        except resolver.ProjectConfigError as exc:
            log.warning("project-config error (%s); using hardcoded memory DB default", exc)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Dataclasses — typed representations of DB rows
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """Typed view of the meta table. Validated at startup."""

    schema_version: int
    embedding_model: str
    embedding_dim: int

    @classmethod
    def load(cls, conn: sqlite3.Connection) -> "Config":
        rows = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        return cls(
            schema_version=int(rows["schema_version"]),
            embedding_model=rows["embedding_model"],
            embedding_dim=int(rows["embedding_dim"]),
        )

    def assert_compatible(self, *, expected_model: str = EMBEDDING_MODEL, expected_dim: int = EMBEDDING_DIM) -> None:
        if self.embedding_model != expected_model:
            raise ValueError(
                f"Embedding model mismatch: DB says {self.embedding_model!r}, "
                f"code expects {expected_model!r}. Run `memory doctor` for details."
            )
        if self.embedding_dim != expected_dim:
            raise ValueError(
                f"Embedding dim mismatch: DB says {self.embedding_dim}, "
                f"code expects {expected_dim}."
            )


@dataclass(frozen=True)
class Case:
    """A single case record from cases_raw."""

    case_id: int
    phase: str
    case_type: str | None
    status: str
    reward: float
    created: int
    updated: int
    project: str | None
    title: str | None
    query: str
    plan: str | None
    outcome: str | None
    tags: list[str] = field(default_factory=list)
    injection_summary: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row | tuple) -> "Case":
        # Order matches `SELECT * FROM cases_raw` minus trajectory (not surfaced to LLMs)
        return cls(
            case_id=row["case_id"],
            phase=row["phase"],
            case_type=row["case_type"],
            status=row["status"],
            reward=row["reward"],
            created=row["created"],
            updated=row["updated"],
            project=row["project"],
            title=row["title"],
            query=row["query"],
            plan=row["plan"],
            outcome=row["outcome"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            injection_summary=row["injection_summary"],
        )

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "phase": self.phase,
            "case_type": self.case_type,
            "status": self.status,
            "reward": self.reward,
            "created": self.created,
            "updated": self.updated,
            "project": self.project,
            "title": self.title,
            "query": self.query,
            "plan": self.plan,
            "outcome": self.outcome,
            "tags": self.tags,
            "injection_summary": self.injection_summary,
        }


@dataclass(frozen=True)
class Signal:
    signal_id: int
    case_id: int
    signal_type: str
    value: float
    source: str | None
    created: int
    metadata: dict | None

    @classmethod
    def from_row(cls, row: sqlite3.Row | tuple) -> "Signal":
        return cls(
            signal_id=row["signal_id"],
            case_id=row["case_id"],
            signal_type=row["signal_type"],
            value=row["value"],
            source=row["source"],
            created=row["created"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )


# ---------------------------------------------------------------------------
# VectorIndex protocol — abstraction over the vector store
# ---------------------------------------------------------------------------


@runtime_checkable
class VectorIndex(Protocol):
    """Minimal interface for a vector store. Implementations: SqliteVecIndex (v1)."""

    def upsert(self, case_id: int, phase: str, vec: np.ndarray) -> None: ...

    def search(
        self, query_vec: np.ndarray, phase: str | None, k: int
    ) -> list[tuple[int, float]]:
        """Return [(case_id, distance), ...] sorted by ascending distance."""

    def delete(self, case_id: int) -> None: ...


class SqliteVecIndex:
    """vec0 virtual table backed implementation of VectorIndex."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    @staticmethod
    def _pack(vec: np.ndarray) -> bytes:
        """Pack a float32 numpy array as bytes for sqlite-vec insertion."""
        if vec.dtype != np.float32:
            vec = vec.astype(np.float32)
        return struct.pack(f"{len(vec)}f", *vec)

    def upsert(self, case_id: int, phase: str, vec: np.ndarray) -> None:
        # vec0 has no native UPSERT. Delete + insert.
        self.conn.execute("DELETE FROM cases_vec WHERE case_id = ?", (case_id,))
        self.conn.execute(
            "INSERT INTO cases_vec(case_id, phase, embedding) VALUES (?, ?, ?)",
            (case_id, phase, self._pack(vec)),
        )

    def search(
        self, query_vec: np.ndarray, phase: str | None, k: int
    ) -> list[tuple[int, float]]:
        packed = self._pack(query_vec)
        if phase is not None:
            rows = self.conn.execute(
                "SELECT case_id, distance FROM cases_vec "
                "WHERE embedding MATCH ? AND phase = ? AND k = ? "
                "ORDER BY distance",
                (packed, phase, k),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT case_id, distance FROM cases_vec "
                "WHERE embedding MATCH ? AND k = ? "
                "ORDER BY distance",
                (packed, k),
            ).fetchall()
        return [(row[0], row[1]) for row in rows]

    def delete(self, case_id: int) -> None:
        self.conn.execute("DELETE FROM cases_vec WHERE case_id = ?", (case_id,))


# ---------------------------------------------------------------------------
# Connection + schema init
# ---------------------------------------------------------------------------


def _assert_sqlite_version() -> None:
    if sqlite3.sqlite_version_info < REQUIRED_SQLITE_VERSION:
        raise RuntimeError(
            f"SQLite {'.'.join(map(str, REQUIRED_SQLITE_VERSION))}+ required, "
            f"got {sqlite3.sqlite_version}. Upgrade Python or system SQLite."
        )


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply required PRAGMAs on every connection."""
    conn.executescript(
        """
        PRAGMA foreign_keys=ON;
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        PRAGMA busy_timeout=30000;
        PRAGMA wal_autocheckpoint=1000;
        PRAGMA temp_store=MEMORY;
        PRAGMA mmap_size=268435456;
        PRAGMA cache_size=-65536;
        """
    )


def _create_vec_table(conn: sqlite3.Connection) -> None:
    """Create the sqlite-vec vec0 virtual table.

    Must run AFTER sqlite_vec.load(conn). PARTITION KEY on phase pre-filters
    the vector index before distance calculation — this is the single most
    important performance decision in the schema.
    """
    conn.execute(
        f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS cases_vec USING vec0(
            case_id INTEGER PRIMARY KEY,
            phase TEXT PARTITION KEY,
            embedding float[{EMBEDDING_DIM}] distance_metric=cosine
        )
        """
    )


def _load_sqlite_vec(conn: sqlite3.Connection) -> None:
    """Load the sqlite-vec extension. Raises ImportError if unavailable."""
    try:
        import sqlite_vec  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "sqlite-vec is not installed. "
            "Run: pip install -r skills/memory/scripts/requirements.txt"
        ) from exc
    conn.enable_load_extension(True)
    try:
        sqlite_vec.load(conn)
    finally:
        conn.enable_load_extension(False)


def connect(db_path: Path | None = None, *, readonly: bool = False) -> sqlite3.Connection:
    """Open a connection with all required PRAGMAs and sqlite-vec loaded.

    Does NOT run migrations. Call init_schema() for that.
    """
    _assert_sqlite_version()
    path = db_path if db_path is not None else user_scope_db_path()

    if readonly and path.exists():
        uri = f"file:{path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=30.0, isolation_level=None)
    else:
        conn = sqlite3.connect(str(path), timeout=30.0, isolation_level=None)

    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    _load_sqlite_vec(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Apply all migrations in order. Idempotent."""
    # Apply SQL migrations (plain tables, indexes, triggers)
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(sql_file.read_text())

    # Create vec0 virtual table (requires sqlite_vec loaded — runs separately
    # from the plain SQL migrations because CREATE VIRTUAL TABLE USING vec0
    # would fail in a freshly-opened connection without extension loading.)
    _create_vec_table(conn)


# ---------------------------------------------------------------------------
# Concurrency helpers
# ---------------------------------------------------------------------------


def write_transaction(conn: sqlite3.Connection):
    """Context manager for writes. Uses BEGIN IMMEDIATE to avoid deferred-upgrade races.

    Usage:
        with write_transaction(conn):
            conn.execute("INSERT ...")
    """
    import contextlib

    @contextlib.contextmanager
    def _txn():
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield
            conn.execute("COMMIT")
        except sqlite3.OperationalError:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise

    return _txn()


def retry_on_busy(fn, *, max_attempts: int = 3, base_delay: float = 0.1):
    """Retry a callable up to N times on SQLITE_BUSY with exponential backoff."""
    delay = base_delay
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            # Only retry on real BUSY, not schema errors
            if "database is locked" in str(exc).lower() or getattr(
                exc, "sqlite_errorcode", None
            ) == sqlite3.SQLITE_BUSY if hasattr(sqlite3, "SQLITE_BUSY") else False:
                last_exc = exc
                time.sleep(delay)
                delay *= 2
                continue
            raise
    if last_exc is not None:
        raise last_exc


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def now() -> int:
    """Current unix timestamp as int."""
    return int(time.time())


def detect_project(cwd: Path | None = None) -> str:
    """Return repo name from git, or 'unknown' if not in a git repo.

    Uses subprocess with explicit exception handling (no bare except Exception).
    """
    import subprocess

    cwd = cwd or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return Path(result.stdout.strip()).name or "unknown"
