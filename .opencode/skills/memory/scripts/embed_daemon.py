#!/usr/bin/env python3
"""Unix-socket daemon that holds a fastembed model in memory.

Listens on $XDG_RUNTIME_DIR/rafayels-memory-{uid}/embed.sock (or /tmp fallback)
and responds to JSON requests line-by-line.

Protocol:
    {"action": "ping"}                  -> {"status": "ok", "uptime_seconds": N}
    {"action": "embed", "texts": [...]} -> {"embeddings": [[...], ...], "model": "...", "dim": N}
    {"action": "stop"}                  -> {"status": "stopping"} then exit

The daemon auto-exits after 30 minutes of idle time to free ~300MB RSS.

Single-instance guard: the PID file is locked with fcntl.flock before binding the socket.
If another daemon is already running, this one exits 0 silently.

Run via: python3 embed_daemon.py
Or spawned automatically by embedder.spawn_daemon().
"""

from __future__ import annotations

import fcntl
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

# Import embedder module for cache path + socket helpers. Use sibling import.
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from embedder import daemon_pid_file, daemon_socket_path, model_cache_dir  # noqa: E402

IDLE_TIMEOUT_SECONDS = 30 * 60  # 30 minutes
MAX_REQUEST_BYTES = 4 * 1024 * 1024  # 4 MB per request
MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIM = 384


class EmbedDaemon:
    def __init__(self) -> None:
        self.start_time = time.time()
        self.last_activity = time.time()
        self.embedder = None
        self.lock = threading.Lock()
        self.should_stop = False

    def _load_embedder(self):
        """Lazy-load the fastembed model on first embed request."""
        if self.embedder is not None:
            return
        with self.lock:
            if self.embedder is not None:
                return
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:
                raise RuntimeError(f"fastembed not installed: {exc}") from exc
            self.embedder = TextEmbedding(
                model_name=MODEL_NAME,
                cache_dir=str(model_cache_dir()),
                threads=1,
            )

    def handle_request(self, payload: dict) -> dict:
        self.last_activity = time.time()
        action = payload.get("action")
        if action == "ping":
            return {
                "status": "ok",
                "uptime_seconds": int(time.time() - self.start_time),
                "model": MODEL_NAME,
                "dim": DIM,
            }
        if action == "embed":
            texts = payload.get("texts") or []
            if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
                return {"error": "texts must be a list of strings", "code": "validation"}
            if not texts:
                return {"embeddings": [], "model": MODEL_NAME, "dim": DIM}
            try:
                self._load_embedder()
            except RuntimeError as exc:
                return {"error": str(exc), "code": "embedder_init_failed"}
            try:
                vecs = list(self.embedder.embed(texts, batch_size=64))
            except (RuntimeError, ValueError) as exc:
                return {"error": f"embed failed: {exc}", "code": "embed_failed"}
            return {
                "embeddings": [v.tolist() for v in vecs],
                "model": MODEL_NAME,
                "dim": DIM,
            }
        if action == "stop":
            self.should_stop = True
            return {"status": "stopping"}
        return {"error": f"unknown action: {action!r}", "code": "unknown_action"}


def _read_request(conn: socket.socket) -> dict | None:
    """Read one newline-delimited JSON request from a socket connection."""
    buf = bytearray()
    conn.settimeout(10.0)
    while b"\n" not in buf and len(buf) < MAX_REQUEST_BYTES:
        try:
            chunk = conn.recv(65536)
        except (TimeoutError, OSError):
            return None
        if not chunk:
            break
        buf.extend(chunk)
    line = bytes(buf).split(b"\n", 1)[0]
    if not line:
        return None
    try:
        return json.loads(line.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _send_response(conn: socket.socket, response: dict) -> None:
    try:
        data = (json.dumps(response) + "\n").encode("utf-8")
        conn.sendall(data)
    except OSError:
        pass


def _acquire_single_instance_lock() -> int | None:
    """Take an exclusive flock on the PID file. Return fd if acquired, None if locked.

    Caller must keep the fd open for the lifetime of the daemon.
    """
    pid_file = daemon_pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(pid_file), os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    # Write our PID
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    os.write(fd, f"{os.getpid()}\n".encode("ascii"))
    return fd


def _bind_socket() -> socket.socket:
    """Bind the Unix socket. Removes stale socket file if present."""
    sock_path = daemon_socket_path()
    sock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if sock_path.exists():
        try:
            sock_path.unlink()
        except OSError:
            pass
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(sock_path))
    sock.listen(8)
    sock.settimeout(1.0)  # allow idle-timeout check
    os.chmod(str(sock_path), 0o600)
    return sock


def main() -> int:
    # Single-instance guard
    lock_fd = _acquire_single_instance_lock()
    if lock_fd is None:
        # Another daemon is already running. Exit silently.
        return 0

    daemon = EmbedDaemon()
    try:
        server = _bind_socket()
    except OSError as exc:
        sys.stderr.write(f"[embed_daemon] failed to bind socket: {exc}\n")
        try:
            os.close(lock_fd)
        except OSError:
            pass
        return 1

    try:
        while not daemon.should_stop:
            # Check idle timeout
            if time.time() - daemon.last_activity > IDLE_TIMEOUT_SECONDS:
                break

            try:
                conn, _ = server.accept()
            except TimeoutError:
                continue
            except OSError:
                break

            try:
                payload = _read_request(conn)
                if payload is None:
                    _send_response(conn, {"error": "invalid request", "code": "parse_error"})
                else:
                    response = daemon.handle_request(payload)
                    _send_response(conn, response)
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

        return 0
    finally:
        try:
            server.close()
        except OSError:
            pass
        try:
            daemon_socket_path().unlink()
        except (OSError, FileNotFoundError):
            pass
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(lock_fd)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
