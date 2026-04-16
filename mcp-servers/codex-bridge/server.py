#!/usr/bin/env python3
"""
Codex Bridge MCP Server

Exposes tools that delegate coding tasks to the OpenAI Codex CLI,
enabling Claude Code to spawn Codex agents for implementation work,
code review, and technical Q&A.

Design notes:
- `codex` CLI's `--full-auto` is a *convenience alias* for `--sandbox workspace-write`.
  Passing both is redundant; passing `--full-auto` with a different sandbox is a user
  error. We treat `sandbox_mode` as the source of truth and derive full-auto from it.
- Codex writes JSONL events to stdout when invoked with `--json`. The protocol channel
  is stdout, so stderr is free for human-readable logs (we pass it through unchanged).
- Final message extraction: we prefer `--output-last-message <file>` when available
  (reliable) and fall back to scanning events (heuristic) if the file is empty.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("codex-bridge")


SANDBOX_MODES = ("read-only", "workspace-write", "danger-full-access")


def _build_prompt(task_description: str, file_paths: list[str] | None, context: str | None) -> str:
    parts = [task_description]
    if file_paths:
        parts.append("\n\nRelevant files:\n" + "\n".join(f"- {p}" for p in file_paths))
    if context:
        parts.append(f"\n\nAdditional context:\n{context}")
    return "\n".join(parts)


def _parse_jsonl(raw: str) -> list[dict]:
    events = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"type": "raw", "content": line})
    return events


def _extract_final_message(events: list[dict]) -> str:
    for event in reversed(events):
        if event.get("type") == "message" and "content" in event:
            return event["content"]
        if "message" in event and isinstance(event["message"], dict):
            text = event["message"].get("content") or event["message"].get("text", "")
            if text:
                return text
    return ""


def _extract_approval_requests(events: list[dict]) -> list[dict]:
    reqs = []
    for ev in events:
        if ev.get("type") in ("approval_request", "confirmation_required", "prompt"):
            reqs.append(ev)
        elif "approval" in ev.get("type", ""):
            reqs.append(ev)
    return reqs


def _extract_file_changes(events: list[dict]) -> list[str]:
    changed = set()
    for ev in events:
        if ev.get("type") == "file_change" and "path" in ev:
            changed.add(ev["path"])
        elif ev.get("type") == "tool_call" and ev.get("name") in ("write", "edit", "apply_patch"):
            args = ev.get("arguments", {}) or {}
            path = args.get("file_path") or args.get("path")
            if path:
                changed.add(path)
    return sorted(changed)


def _check_codex_installed() -> str | None:
    """Return error message if codex CLI is missing, else None."""
    if shutil.which("codex") is None:
        return (
            "codex CLI not found on PATH. Install from "
            "https://github.com/openai/codex or `brew install codex`."
        )
    return None


def _discover_working_directory(explicit: str | None) -> str:
    """If caller didn't pass working_directory, walk up from cwd to find the
    git root. Falls back to cwd if no git repo is found. Returns absolute path.
    """
    if explicit:
        return str(Path(explicit).expanduser().resolve())
    start = Path.cwd().resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return str(candidate)
    return str(start)


def _resolve_sandbox(sandbox_mode: str) -> str:
    """Validate sandbox mode; raise ValueError on unknown."""
    if sandbox_mode not in SANDBOX_MODES:
        raise ValueError(
            f"Invalid sandbox_mode {sandbox_mode!r}. Must be one of {SANDBOX_MODES}."
        )
    return sandbox_mode


async def _run_codex(
    cmd: list[str],
    cwd: str | None = None,
    timeout: int = 600,
) -> tuple[int, list[dict], str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd or os.getcwd(),
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        stdout, stderr = await proc.communicate()
        return -1, [], f"Codex timed out after {timeout}s\n{stderr.decode()}"

    events = _parse_jsonl(stdout.decode())
    return proc.returncode or 0, events, stderr.decode()


def _truncate_stderr(stderr: str, success: bool, limit: int = 4000) -> str:
    """Keep full stderr on failure; truncate aggressively on success to save tokens."""
    if success:
        if len(stderr) <= limit:
            return stderr
        return stderr[-limit:] + f"\n... (truncated from {len(stderr)} chars)"
    return stderr


@mcp.tool()
async def delegate_coding_task(
    task_description: str,
    working_directory: str | None = None,
    file_paths: list[str] | None = None,
    context: str | None = None,
    model: str | None = None,
    sandbox_mode: str = "workspace-write",
    timeout: int = 600,
    skip_git_check: bool = False,
    add_writable_dirs: list[str] | None = None,
) -> dict:
    """
    Delegate a coding task to Codex.

    Args:
        task_description: What Codex should do. Be specific.
        working_directory: Absolute path for Codex's cwd. Defaults to server cwd.
        file_paths: Relevant files to reference (appended to the prompt as context).
        context: Extra context (conventions, constraints) appended to the prompt.
        model: Optional Codex model override (e.g., "o3", "gpt-5-codex").
        sandbox_mode: "workspace-write" (default, writes in cwd), "read-only" (Q&A),
                      or "danger-full-access" (use sparingly).
        timeout: Seconds before the Codex process is killed. Default 600 (10min).
        skip_git_check: Pass --skip-git-repo-check for non-git workspaces.
        add_writable_dirs: Extra directories Codex may write to (passed as --add-dir).

    Returns a dict with:
        status: "success" | "error" | "needs_approval"
        returncode: exit code from codex
        final_message: Codex's last user-facing message
        file_changes: files Codex modified (best-effort from events)
        approval_requests: prompts Codex emitted (should be empty in workspace-write)
        events: tail of event stream (max 50 events)
        stderr: stderr from codex (truncated on success)
    """
    if err := _check_codex_installed():
        return {"status": "error", "returncode": -1, "final_message": "", "error": err,
                "file_changes": [], "approval_requests": [], "events": [], "stderr": ""}

    try:
        sandbox = _resolve_sandbox(sandbox_mode)
    except ValueError as e:
        return {"status": "error", "returncode": -1, "final_message": "", "error": str(e),
                "file_changes": [], "approval_requests": [], "events": [], "stderr": ""}

    working_directory = _discover_working_directory(working_directory)

    prompt = _build_prompt(task_description, file_paths, context)

    # Reliable final-message extraction: write to a tmpfile and read it back.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, prefix="codex-last-"
    ) as f:
        last_msg_file = Path(f.name)

    try:
        cmd = ["codex", "exec", "--sandbox", sandbox]
        if model:
            cmd.extend(["-m", model])
        if working_directory:
            cmd.extend(["-C", working_directory])
        if skip_git_check:
            cmd.append("--skip-git-repo-check")
        if add_writable_dirs:
            for d in add_writable_dirs:
                cmd.extend(["--add-dir", d])
        cmd.extend(["--json", "--color", "never"])
        cmd.extend(["-o", str(last_msg_file)])
        cmd.append(prompt)

        returncode, events, stderr = await _run_codex(
            cmd, cwd=working_directory, timeout=timeout
        )

        approvals = _extract_approval_requests(events)
        final_msg = ""
        try:
            final_msg = last_msg_file.read_text().strip()
        except OSError:
            pass
        if not final_msg:
            final_msg = _extract_final_message(events)

        if returncode == 0:
            status = "success"
        elif approvals:
            status = "needs_approval"
        else:
            status = "error"

        return {
            "status": status,
            "returncode": returncode,
            "final_message": final_msg,
            "approval_requests": approvals,
            "file_changes": _extract_file_changes(events),
            "events": events[-50:] if len(events) > 50 else events,
            "stderr": _truncate_stderr(stderr, success=(returncode == 0)),
        }
    finally:
        last_msg_file.unlink(missing_ok=True)


@mcp.tool()
async def codex_review_code(
    file_paths: list[str] | None = None,
    working_directory: str | None = None,
    review_focus: str | None = None,
    model: str | None = None,
    timeout: int = 600,
) -> dict:
    """
    Ask Codex to review code in the current repository or specific files.

    Uses `codex exec review` (non-interactive review subcommand).
    """
    if err := _check_codex_installed():
        return {"status": "error", "returncode": -1, "final_message": "", "error": err,
                "events": [], "stderr": ""}

    cmd = ["codex", "exec", "review", "--json", "--color", "never"]
    if model:
        cmd.extend(["-m", model])
    if working_directory:
        cmd.extend(["-C", working_directory])

    prompt = review_focus or "Review the provided code for bugs, style issues, and improvements."
    if file_paths:
        prompt += "\n\nFocus on these files:\n" + "\n".join(f"- {p}" for p in file_paths)
    cmd.append(prompt)

    returncode, events, stderr = await _run_codex(cmd, cwd=working_directory, timeout=timeout)

    return {
        "status": "success" if returncode == 0 else "error",
        "returncode": returncode,
        "final_message": _extract_final_message(events),
        "events": events[-50:] if len(events) > 50 else events,
        "stderr": _truncate_stderr(stderr, success=(returncode == 0)),
    }


@mcp.tool()
async def codex_answer_question(
    question: str,
    working_directory: str | None = None,
    file_paths: list[str] | None = None,
    model: str | None = None,
    timeout: int = 120,
) -> dict:
    """
    Ask Codex a technical question about the codebase.

    Runs Codex in read-only sandbox mode. Ideal for quick clarifications
    before deciding whether to delegate implementation.
    """
    if err := _check_codex_installed():
        return {"status": "error", "returncode": -1, "answer": "", "error": err,
                "events": [], "stderr": ""}

    prompt = _build_prompt(question, file_paths, None)

    cmd = ["codex", "exec", "--sandbox", "read-only", "--json", "--color", "never"]
    if model:
        cmd.extend(["-m", model])
    if working_directory:
        cmd.extend(["-C", working_directory])
    cmd.append(prompt)

    returncode, events, stderr = await _run_codex(cmd, cwd=working_directory, timeout=timeout)

    return {
        "status": "success" if returncode == 0 else "error",
        "returncode": returncode,
        "answer": _extract_final_message(events),
        "events": events[-30:] if len(events) > 30 else events,
        "stderr": _truncate_stderr(stderr, success=(returncode == 0)),
    }


@mcp.tool()
async def get_codex_version() -> dict:
    """Return the installed Codex CLI version, or an error if not installed."""
    if err := _check_codex_installed():
        return {"status": "error", "version": "", "error": err}

    proc = await asyncio.create_subprocess_exec(
        "codex", "--version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return {
        "version": stdout.decode().strip(),
        "status": "ok" if proc.returncode == 0 else "error",
        "stderr": stderr.decode(),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
