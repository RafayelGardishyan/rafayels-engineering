---
name: codex
description: Delegate a coding task to OpenAI Codex via the codex-bridge MCP server. Use for pure-coding tasks with clear requirements.
argument-hint: "[task description]"
disable-model-invocation: true
---

# /codex — Delegate to Codex

Hand off a coding task to OpenAI Codex via the `codex-bridge` MCP server.

## Usage

```
/codex Add a retry wrapper to the API client with exponential backoff
/codex Review src/auth.ts for security issues
/codex Refactor the user service to use dependency injection
```

## Workflow

1. **Parse the task** from `$ARGUMENTS`. If it's empty, ask the user what to delegate.
2. **Identify relevant files** by searching the codebase (`Grep`, `Glob`, or
   `Read` on an obvious path). Gather 1–5 paths that give Codex enough grounding.
3. **Pick the right tool**:
   - `mcp__codex-bridge__delegate_coding_task` — implementation work (default).
   - `mcp__codex-bridge__codex_review_code` — when the task is clearly a review.
   - `mcp__codex-bridge__codex_answer_question` — when the user wants an
     explanation, not a change.
4. **Call the tool** with:
   - `task_description` — the user's task, expanded with any clarification you
     gathered.
   - `working_directory` — the absolute path to the repo root (use `pwd`).
   - `file_paths` — the files you identified in step 2.
   - `context` — any project conventions the task should follow.
   - Leave other args at defaults unless you have a reason.
5. **Verify the result**:
   - Check `file_changes` matches what the task asked for.
   - `Read` or `git diff` each modified file.
   - Run tests if they exist.
6. **Report back**:
   - What Codex changed (list files).
   - Whether the diff looks right.
   - Any follow-ups needed.

## Example

User: `/codex Add a loading skeleton to the dashboard page`

Steps:

1. Find the file: `Glob "**/dashboard/page.tsx"` → `app/dashboard/page.tsx`.
2. Check for an existing skeleton pattern: `Grep "Skeleton" --type tsx`.
3. Call the tool:

   ```text
   mcp__codex-bridge__delegate_coding_task({
     task_description: "Add a loading skeleton to app/dashboard/page.tsx. Use the existing <Skeleton /> component from app/components/ui/skeleton.tsx. Match the layout of the real dashboard so the skeleton reserves the same space.",
     working_directory: "/Users/me/repo",
     file_paths: [
       "app/dashboard/page.tsx",
       "app/components/ui/skeleton.tsx"
     ],
     context: "Next.js 14 app router. Use Suspense for the skeleton boundary."
   })
   ```

4. On return: `git diff app/dashboard/page.tsx` to verify.
5. Report: "Codex added a `<DashboardSkeleton />` component using the existing
   `Skeleton` primitive, wrapped the page body in `<Suspense>`. Diff looks
   correct — no new deps added. Ready to commit."

## Tips

- If the task spans many files, **split it** into two or three `/codex` calls.
  One concern per delegation lands better than a mega-prompt.
- If Codex returns `status: "needs_approval"`, the sandbox blocked something.
  Check `approval_requests`, then either narrow the task or pass
  `add_writable_dirs`.
- Never say "done" based on `final_message` alone — always verify the diff
  yourself before reporting success to the user.

## Related

- `delegate-to-codex` skill — full reference with all tool parameters, sandbox
  modes, troubleshooting.
- `codex-delegate` agent — use via `Agent(subagent_type: "rafayels-engineering:codex-delegate", ...)` when you want a separate agent to own the delegation lifecycle.
