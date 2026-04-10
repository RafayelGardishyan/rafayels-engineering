"""Embedder: fastembed wrapper with optional Unix-socket daemon client.

Architecture:
    memory CLI  ──(JSON over socket)──> embed_daemon.py (persistent fastembed)
                 └── (fallback) ──────> in-process fastembed (cold start)

The daemon is the preferred path (warm ~10ms). In-process fallback activates
if daemon is unreachable — CLI still works, just slower.

Exceptions are specific (ConnectionRefusedError, ImportError, etc.).
No bare `except Exception`.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import numpy as np


class EmbedderUnavailable(RuntimeError):
    """Raised when neither daemon nor in-process embedder can be used.

    Callers (retrieve, capture) should catch this and degrade gracefully
    (skip retrieval / skip write). The CLI boundary converts this to exit 75.
    """


def model_cache_dir() -> Path:
    """Return the fastembed model cache directory."""
    path = Path.home() / ".cache" / "rafayels-memory" / "fastembed"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def daemon_socket_path() -> Path:
    """Return the Unix socket path for the embedder daemon."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir and Path(runtime_dir).exists():
        base = Path(runtime_dir)
    else:
        # macOS fallback: XDG_RUNTIME_DIR is often unset
        base = Path(f"/tmp/rafayels-memory-{os.getuid()}")
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
    return base / "embed.sock"


def daemon_pid_file() -> Path:
    """Lock file for single-instance daemon guard."""
    sock = daemon_socket_path()
    return sock.with_suffix(".pid")


# ---------------------------------------------------------------------------
# Daemon client
# ---------------------------------------------------------------------------


def _send_to_daemon(
    payload: dict, *, socket_path: Path | None = None, timeout: float = 10.0
) -> dict:
    """Send a single JSON request to the daemon and return the JSON response.

    Raises ConnectionRefusedError if the daemon is not listening.
    Raises TimeoutError if the request times out.
    """
    sock_path = socket_path or daemon_socket_path()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(str(sock_path))
        msg = (json.dumps(payload) + "\n").encode("utf-8")
        sock.sendall(msg)
        # Read until newline
        chunks: list[bytes] = []
        while True:
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)
            if b"\n" in data:
                break
        raw = b"".join(chunks).split(b"\n", 1)[0]
        if not raw:
            raise ConnectionRefusedError("daemon returned empty response")
        return json.loads(raw.decode("utf-8"))
    finally:
        try:
            sock.close()
        except OSError:
            pass


def ping_daemon(*, timeout: float = 1.0) -> bool:
    """Return True if the daemon is reachable and responds to ping."""
    try:
        resp = _send_to_daemon({"action": "ping"}, timeout=timeout)
        return resp.get("status") == "ok"
    except (ConnectionRefusedError, FileNotFoundError, TimeoutError, OSError):
        return False


def spawn_daemon(*, wait_seconds: float = 3.0) -> bool:
    """Spawn the embedder daemon if not already running.

    Returns True if the daemon is reachable after spawn, False otherwise.
    Uses a PID file + file lock to prevent double-spawn races.
    """
    import fcntl

    if ping_daemon():
        return True

    pid_file = daemon_pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # Open (or create) the PID file and take an exclusive non-blocking lock.
    # If another process holds the lock, it's spawning — wait for it.
    try:
        lock_fd = os.open(str(pid_file), os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return False

    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Another process holds the lock — wait for it to finish spawning
            os.close(lock_fd)
            deadline = time.time() + wait_seconds
            while time.time() < deadline:
                if ping_daemon():
                    return True
                time.sleep(0.1)
            return ping_daemon()

        # We have the lock. Check again in case another process finished
        # between our first ping and acquiring the lock.
        if ping_daemon():
            return True

        # Spawn the daemon as a detached process
        daemon_script = Path(__file__).parent / "embed_daemon.py"
        if not daemon_script.exists():
            return False

        # Use Popen with start_new_session to fully detach
        with open(os.devnull, "rb") as devnull_in, open(os.devnull, "wb") as devnull_out:
            subprocess.Popen(
                [sys.executable, str(daemon_script)],
                stdin=devnull_in,
                stdout=devnull_out,
                stderr=devnull_out,
                start_new_session=True,
            )

        # Wait for socket to appear
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if ping_daemon():
                return True
            time.sleep(0.1)
        return False
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(lock_fd)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# In-process fallback
# ---------------------------------------------------------------------------

_in_process_embedder = None


def _get_in_process_embedder():
    """Lazily load and cache an in-process TextEmbedding instance."""
    global _in_process_embedder
    if _in_process_embedder is not None:
        return _in_process_embedder
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise EmbedderUnavailable(
            "fastembed is not installed. "
            "Run: pip install -r skills/memory/scripts/requirements.txt"
        ) from exc
    try:
        _in_process_embedder = TextEmbedding(
            model_name="BAAI/bge-small-en-v1.5",
            cache_dir=str(model_cache_dir()),
            threads=1,
        )
    except (OSError, RuntimeError) as exc:
        raise EmbedderUnavailable(
            f"Failed to initialize fastembed: {exc}. "
            "Check network connectivity or delete corrupt model cache at "
            f"{model_cache_dir()}"
        ) from exc
    return _in_process_embedder


def _embed_in_process(texts: list[str]) -> list[np.ndarray]:
    """Embed texts using an in-process fastembed instance."""
    embedder = _get_in_process_embedder()
    return [np.asarray(v, dtype=np.float32) for v in embedder.embed(texts, batch_size=64)]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def embed(texts: list[str], *, prefer_daemon: bool = True) -> list[np.ndarray]:
    """Embed one or more texts. Tries daemon first, falls back to in-process.

    Raises EmbedderUnavailable if both paths fail.
    """
    if not texts:
        return []

    if prefer_daemon:
        # Try existing daemon
        try:
            resp = _send_to_daemon({"action": "embed", "texts": texts}, timeout=30.0)
            if "embeddings" in resp:
                return [np.asarray(v, dtype=np.float32) for v in resp["embeddings"]]
        except (ConnectionRefusedError, FileNotFoundError, TimeoutError, OSError):
            pass

        # Try spawning daemon
        if spawn_daemon(wait_seconds=3.0):
            try:
                resp = _send_to_daemon(
                    {"action": "embed", "texts": texts}, timeout=30.0
                )
                if "embeddings" in resp:
                    return [np.asarray(v, dtype=np.float32) for v in resp["embeddings"]]
            except (ConnectionRefusedError, FileNotFoundError, TimeoutError, OSError):
                pass

    # Fall back to in-process
    return _embed_in_process(texts)


def stop_daemon() -> bool:
    """Request the daemon to stop. Returns True if request was accepted."""
    try:
        resp = _send_to_daemon({"action": "stop"}, timeout=2.0)
        return resp.get("status") == "stopping"
    except (ConnectionRefusedError, FileNotFoundError, TimeoutError, OSError):
        return False
