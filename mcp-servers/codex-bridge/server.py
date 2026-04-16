#!/usr/bin/env python3
"""
Codex Bridge MCP Server

Exposes tools that delegate coding tasks to the OpenAI Codex CLI,
enabling Claude Code to spawn Codex agents for implementation work,
code review, and technical Q&A.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("codex-bridge")


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
        elif ev.get("type") == "tool_call" and ev.get("name") in ("write", "edit"):
            path = ev.get("arguments", {}).get("file_path") or ev.get("arguments", {}).get("path")
            if path:
                changed.add(path)
    return sorted(changed)


async def _run_codex(
    cmd: list[str],
    cwd: str | None = None,
    timeout: int = 300,
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


@mcp.tool()
async def delegate_coding_task(
    task_description: str,
    working_directory: str | None = None,
    file_paths: list[str] | None = None,
    context: str | None = None,
    model: str | None = None,
    full_auto: bool = True,
    sandbox_mode: str = "workspace-write",
) -> dict:
    """
    Delegate a coding task to Codex.

    Codex will receive the task description, optionally read the provided
    file paths for context, and attempt to implement the requested changes.
    Returns structured events so Claude can see what Codex did and respond.
    """
    prompt = _build_prompt(task_description, file_paths, context)

    cmd = ["codex", "exec"]
    if full_auto:
        cmd.append("--full-auto")
    cmd.extend(["--sandbox", sandbox_mode])
    if model:
        cmd.extend(["-m", model])
    if working_directory:
        cmd.extend(["-C", working_directory])
    cmd.extend(["--json", "--color", "never"])
    cmd.append(prompt)

    returncode, events, stderr = await _run_codex(cmd, cwd=working_directory)

    approvals = _extract_approval_requests(events)
    status = "success" if returncode == 0 and not approvals else "needs_approval" if approvals else "error"

    return {
        "status": status,
        "returncode": returncode,
        "final_message": _extract_final_message(events),
        "approval_requests": approvals,
        "file_changes": _extract_file_changes(events),
        "events": events[-50:] if len(events) > 50 else events,  # truncate for size
        "stderr": stderr,
    }


@mcp.tool()
async def codex_review_code(
    file_paths: list[str] | None = None,
    working_directory: str | None = None,
    review_focus: str | None = None,
    model: str | None = None,
) -> dict:
    """
    Ask Codex to review code in the current repository or specific files.

    Codex runs `codex exec review` non-interactively and returns findings.
    """
    cmd = ["codex", "exec", "review", "--json", "--color", "never"]
    if model:
        cmd.extend(["-m", model])
    if working_directory:
        cmd.extend(["-C", working_directory])

    prompt = review_focus or "Review the provided code for bugs, style issues, and improvements."
    if file_paths:
        prompt += "\n\nFocus on these files:\n" + "\n".join(f"- {p}" for p in file_paths)

    # exec review doesn't take a prompt arg directly, so we pipe it via stdin concept
    # but codex exec [PROMPT] accepts a prompt. For review, we can use exec review with prompt appended
    cmd.append(prompt)

    returncode, events, stderr = await _run_codex(cmd, cwd=working_directory)

    return {
        "status": "success" if returncode == 0 else "error",
        "returncode": returncode,
        "final_message": _extract_final_message(events),
        "events": events[-50:] if len(events) > 50 else events,
        "stderr": stderr,
    }


@mcp.tool()
async def codex_answer_question(
    question: str,
    working_directory: str | None = None,
    file_paths: list[str] | None = None,
    model: str | None = None,
) -> dict:
    """
    Ask Codex a technical question about the codebase.

    Runs Codex in a lightweight, non-mutating mode. Ideal for quick
    clarifications before deciding whether to delegate implementation.
    """
    prompt = _build_prompt(question, file_paths, None)

    cmd = ["codex", "exec", "--sandbox", "read-only", "--json", "--color", "never"]
    if model:
        cmd.extend(["-m", model])
    if working_directory:
        cmd.extend(["-C", working_directory])
    cmd.append(prompt)

    returncode, events, stderr = await _run_codex(cmd, cwd=working_directory, timeout=60)

    return {
        "status": "success" if returncode == 0 else "error",
        "returncode": returncode,
        "answer": _extract_final_message(events),
        "events": events[-30:] if len(events) > 30 else events,
        "stderr": stderr,
    }


@mcp.tool()
async def get_codex_version() -> dict:
    """Return the installed Codex CLI version."""
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
    mcp.run("stdio")
