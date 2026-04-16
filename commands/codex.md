---
name: codex
description: Delegate a coding task to the OpenAI Codex CLI agent. Use when you want Codex to write, review, or refactor code for you.
argument-hint: "[task description]"
disable-model-invocation: true
---

# /codex — Delegate to Codex

Quickly hand off a coding task to OpenAI Codex via the codex-bridge MCP server.

## Usage

```
/codex Add a retry wrapper to the API client with exponential backoff
/codex Review src/auth.ts for security issues
/codex Refactor the user service to use dependency injection
```

## Workflow

1. **Parse the user's task** from `$ARGUMENTS`
2. **Identify relevant files** by searching the codebase
3. **Call the codex-bridge MCP server** using `delegate_coding_task`
4. **Summarize results** for the user, including file changes and any follow-ups needed

## Tool Selection

- Default to **`delegate_coding_task`** for implementation requests
- Use **`codex_review_code`** if the prompt is clearly a review request
- Use **`codex_answer_question`** if the user just wants a technical explanation

## Example

**User:** `/codex Add a loading skeleton to the dashboard page`

**Action:**
1. Find the dashboard page file (`app/dashboard/page.tsx` or similar)
2. Call `delegate_coding_task` with the task description and file path
3. Report back:
   - What Codex changed
   - Which files were modified
   - Whether any follow-up is needed
