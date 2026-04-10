"""Tests for embedder.py: daemon client, in-process fallback, error paths.

These tests don't require fastembed to be installed — they test the error
paths and connection logic with mocked socket / subprocess calls.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from embedder import (
    EmbedderUnavailable,
    daemon_pid_file,
    daemon_socket_path,
    model_cache_dir,
    ping_daemon,
)


def test_model_cache_dir_returns_path():
    path = model_cache_dir()
    assert isinstance(path, Path)
    assert "rafayels-memory" in str(path)


def test_daemon_socket_path_returns_path():
    path = daemon_socket_path()
    assert isinstance(path, Path)
    assert path.name == "embed.sock"


def test_daemon_pid_file_alongside_socket():
    sock = daemon_socket_path()
    pid = daemon_pid_file()
    assert pid.parent == sock.parent
    assert pid.suffix == ".pid"


def test_ping_daemon_returns_false_when_no_socket():
    with patch("embedder.daemon_socket_path") as mock_path:
        mock_path.return_value = Path("/tmp/nonexistent-socket-xyz")
        assert ping_daemon() is False


def test_embedder_unavailable_is_runtime_error():
    # EmbedderUnavailable should inherit from RuntimeError so callers can
    # catch it as a specific exception
    assert issubclass(EmbedderUnavailable, RuntimeError)
