---
name: delegate-to-codex
description: Delegate coding tasks to the OpenAI Codex CLI via the codex-bridge MCP server. Use when the user asks to use Codex, for pure-coding spikes with clear requirements, or when parallelizing implementation work across AI agents.
---

# Delegate to Codex

Use the `codex-bridge` MCP server to hand off coding tasks to OpenAI Codex.
Claude frames the task and reviews results; Codex does the typing.

## Quick Start — One-Liner Delegation

The minimum viable call is just a task description. The server auto-discovers
the git root for `working_directory`:

```text
mcp__codex-bridge__delegate_coding_task({
  task_description: "Add a --dry-run flag to scripts/deploy.sh that logs the commands it would run without executing them."
})
```

That's it. For better results, pass `file_paths` so Codex knows where to look.
For large refactors, bump `timeout` (default 600s).

**Fallback when the MCP server isn't loaded:** use `bin/codex-delegate` from a
shell — same contract, works without Claude Code.

```bash
bin/codex-delegate "task description here"
bin/codex-delegate --files src/foo.ts --timeout 1200 "refactor task"
```

## When to Delegate

Delegate to Codex when:

- The task is **pure coding** with a clear spec (implement X, refactor Y, add test Z).
- You have the **file paths** Codex needs to read.
- The work is **self-contained** — Codex finishes in one shot or a bounded iteration loop.
- The user explicitly says "use Codex" / "delegate to Codex".
- You want a **second opinion** on an implementation approach.

Keep it on Claude when:

- The task requires brainstorming, planning, or architectural judgment.
- Deep project-convention knowledge matters more than typing speed.
- The work is security-sensitive and needs line-by-line human review.
- The task spans many loosely-coupled changes (break it up before delegating).

## The Four MCP Tools

The `codex-bridge` server registers these tools. In Claude Code, they surface as
`mcp__codex-bridge__<tool>` (exact names depend on platform — check available
tools if unsure).

### `delegate_coding_task` — the workhorse

```json
{
  "task_description": "Implement a retry wrapper around fetch with exponential backoff.",
  "working_directory": "/absolute/path/to/repo",
  "file_paths": ["src/api/client.ts", "src/utils/logger.ts"],
  "context": "Use the existing logger in src/utils/logger.ts. Match the style of src/api/auth.ts.",
  "sandbox_mode": "workspace-write",
  "timeout": 600,
  "skip_git_check": false,
  "add_writable_dirs": []
}
```

**Required:** `task_description`.

**Strongly recommended:** `working_directory` (absolute path — don't rely on cwd),
`file_paths` (gives Codex the grounding it needs).

**Sandbox modes** (pick one; they're mutually exclusive with "full-auto" — the
server handles the mapping):

| Mode | When to use |
|---|---|
| `workspace-write` (default) | Codex may read/write inside `working_directory`. This is the "full-auto" equivalent. |
| `read-only` | Codex reads but cannot modify files. Use for Q&A or diagnostic tasks. Prefer `codex_answer_question` though. |
| `danger-full-access` | No sandbox. Only when you have strong reason and have reviewed the task. |

**Other knobs:**

- `timeout` (seconds) — default 600 (10min). Bump for multi-file refactors.
- `skip_git_check` — needed when `working_directory` is outside a git repo.
- `add_writable_dirs` — extra dirs Codex may write to (e.g., a sibling fixtures dir).
- `model` — Codex model override. Usually leave unset.

**Response shape:**

```json
{
  "status": "success" | "error" | "needs_approval",
  "returncode": 0,
  "final_message": "Codex's one-paragraph summary of what it did",
  "file_changes": ["src/api/client.ts", "src/api/client.test.ts"],
  "approval_requests": [],
  "events": [...],
  "stderr": "..."
}
```

### `codex_review_code` — ask Codex to review

```json
{
  "file_paths": ["src/auth/middleware.ts"],
  "working_directory": "/abs/path",
  "review_focus": "Check for timing attacks and secure session handling."
}
```

Returns Codex's review as `final_message`.

### `codex_answer_question` — non-mutating Q&A

```json
{
  "question": "What's the difference between these two patterns?",
  "file_paths": ["src/pattern-a.ts", "src/pattern-b.ts"],
  "working_directory": "/abs/path"
}
```

Runs in `read-only` sandbox. Returns `answer`. Use this before `delegate_coding_task`
when you're unsure how the existing code works.

### `get_codex_version` — smoke test

Call once if you're unsure Codex is installed — errors clearly if the CLI is missing.

## Workflow

1. **Frame the task.** Write a description Codex could follow without asking
   questions: what, where, constraints. Include file paths.
2. **Call `delegate_coding_task`** (or one of the others) via the MCP tool.
3. **Wait for the response.** Default timeout is 10min; Codex usually finishes
   faster.
4. **Verify the diff.** Do NOT trust `final_message` alone — always inspect:
   - `file_changes` (the files Codex touched)
   - `git diff` or `Read` each modified file
5. **Iterate if needed.** If Codex's first pass is incomplete, call again with a
   refined prompt that references what's missing. Include the file paths again.
6. **Integrate.** Commit Codex's work with a proper message; do not claim it's
   done until you've verified it runs/tests pass.

## Best Practices

**Task framing:**

- One concern per delegation. Split "add feature + write tests + update docs" into
  two or three calls. Smaller tasks finish faster and fail more cheaply.
- Give Codex the **positive** spec ("do X") plus relevant **negative** constraints
  ("don't touch Y", "don't add dependencies").
- Paste schemas, enums, or existing function signatures directly into `context` —
  Codex doesn't need to go find them.

**File paths:**

- Always pass `file_paths` for files Codex must read or write.
- Use absolute paths in `working_directory`; use relative paths in `file_paths`.

**Verification:**

- `status: "success"` means Codex exited 0, not that the work is correct.
- Read the diff. If tests exist, run them. If not, ask Codex to add tests.
- Check for surprises: new deps in `package.json`/`requirements.txt`, new files
  outside the expected area, deleted files.

**Iteration:**

- If the first pass misses something, a follow-up call with the new scope works
  better than a "fix what you just did" prompt — Codex handles fresh specs cleaner
  than self-correction.

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `error: codex CLI not found on PATH` | Codex not installed | `brew install codex` or see https://github.com/openai/codex |
| `Codex timed out after 600s` | Large task, default timeout too short | Pass `timeout: 1800` (30min) or split the task |
| `status: needs_approval` with prompts | Sandbox blocked a write | Either adjust `sandbox_mode` or add the dir via `add_writable_dirs` |
| `file_changes` empty but `final_message` says "done" | Event schema mismatch | Run `git status` / `git diff` — the files are probably there; the event parser missed them |
| Codex refuses to run, says "not a git repo" | Working dir is outside a git repo | Pass `skip_git_check: true` |
| stderr is huge and noisy | Codex CLI verbose logs | The server truncates stderr to last 4KB on success; on failure, full stderr is returned |
| Sandbox confusion (`full_auto` vs `sandbox_mode`) | `full_auto` used to be a separate param | Removed — just set `sandbox_mode`. Default (`workspace-write`) is the old full-auto. |

## Example: delegating a Phase-1 scaffold

```text
delegate_coding_task({
  task_description:
    "Create skills/foo/scripts/resolver.py implementing the API in "
    "docs/plans/2026-04-16-feat-foo-plan.md § 'Resolver API shape'. "
    "Also create scripts/tests/test_resolver.py with the 8 test cases "
    "listed in § 'Phase 1: Scaffold resolver + tests'.",
  working_directory: "/Users/me/repo/.worktrees/feat/foo",
  file_paths: [
    "docs/plans/2026-04-16-feat-foo-plan.md",
    "skills/bar/scripts/db.py"  // pattern reference
  ],
  context:
    "Python 3.10+. from __future__ import annotations at top. Use pyyaml, no other deps. "
    "Tests must pass with `pytest tests/` from scripts/."
})
```

After the call returns:

1. Check `file_changes` lists the files you expected.
2. `Read` or `git diff` each one.
3. `cd scripts && pytest tests/` and confirm green.
4. Commit.

## When the Bridge Itself Breaks

If `delegate_coding_task` returns structured errors consistently:

1. `get_codex_version` — confirm the CLI is installed and authenticated.
2. `codex exec --help` in a shell — confirm the flags this server passes still exist
   (CLI changes can break the bridge).
3. Check `mcp-servers/codex-bridge/server.py` — the flag list lives in `_run_codex`
   and `delegate_coding_task`. File an issue with codex CLI output if the flags
   have drifted.

## Related

- `/codex` command — one-shot delegation from chat.
- `codex-delegate` agent (`agents/codex-delegate.md`) — subagent that calls the
  bridge and reports back. Use when you want a separate agent to handle the whole
  delegation lifecycle.
- `/workflows:work` — references Codex delegation as the default path for pure
  coding tasks during Phase 2 task execution.
