---
name: delegate-to-codex
description: Delegate coding tasks to the OpenAI Codex CLI agent. Use when the user explicitly asks to use Codex, for quick code generation spikes, or when parallelizing implementation work across multiple AI agents.
---

# Delegate to Codex

Use the Codex Bridge MCP server to hand off coding tasks to OpenAI Codex.
This enables Claude and Codex to communicate: Claude delegates, Codex executes,
and Codex returns structured results so Claude can review, iterate, or ship.

## When to Delegate

- User explicitly says "use Codex" or "delegate to Codex"
- Pure coding tasks with clear requirements (implement X, refactor Y, add Z)
- You want a second AI opinion on implementation approach
- Time-boxed spikes where parallel execution is valuable
- Tasks that are bottlenecked on typing speed rather than architecture

## When NOT to Delegate

- Brainstorming or planning (these stay with Claude)
- Complex architectural decisions requiring vault/ADR context
- Tasks needing deep project-specific convention knowledge
- Security-sensitive changes without human review

## Available MCP Tools

### `delegate_coding_task`

Primary tool for implementation work.

```json
{
  "task_description": "Implement a retry wrapper around fetch with exponential backoff",
  "working_directory": ".",
  "file_paths": ["src/api/client.ts"],
  "context": "Use the existing logger in src/utils/logger.ts",
  "full_auto": true,
  "sandbox_mode": "workspace-write"
}
```

**Response fields:**
- `status`: `success`, `error`, or `needs_approval`
- `final_message`: Codex's summary of what it did
- `file_changes`: List of files Codex touched
- `events`: Structured JSONL events from Codex (last 50)
- `approval_requests`: Any prompts Codex emitted (rare in full-auto mode)

### `codex_review_code`

Ask Codex to review specific files or the whole repo.

```json
{
  "file_paths": ["src/auth/middleware.ts"],
  "review_focus": "Check for timing attacks and secure session handling"
}
```

### `codex_answer_question`

Non-mutating Q&A. Great for quick clarifications.

```json
{
  "question": "What is the difference between these two patterns in this codebase?",
  "file_paths": ["src/pattern-a.ts", "src/pattern-b.ts"]
}
```

## Communication Loop

1. **Claude decides** whether a task is a good fit for Codex
2. **Claude calls** the appropriate MCP tool with full context
3. **Codex executes** in its own sandboxed process
4. **Claude receives** structured results (messages, file changes, errors)
5. **Claude responds** to the user with a summary, or iterates by calling again

This is bidirectional: Codex's output becomes part of Claude's context,
and Claude can follow up with refined prompts or additional tasks.

## Best Practices

- **Provide file context**: Always include `file_paths` so Codex knows what to read
- **Use `full_auto: true`** for autonomous coding; set to `false` only if you want Codex to pause for approvals
- **Keep tasks focused**: One feature or one file at a time works better than megaprompts
- **Review file changes**: Check `file_changes` in the response before telling the user it's done
- **Iterate**: If Codex's first attempt is incomplete, call again with a follow-up prompt

## Example Workflow

```javascript
// 1. Delegate implementation
MCP({
  server: "codex-bridge",
  tool: "delegate_coding_task",
  arguments: {
    task_description: "Add input validation to the signup form using zod",
    file_paths: ["app/routes/signup.tsx"],
    context: "Follow the validation pattern used in app/routes/login.tsx"
  }
})

// 2. Review what Codex changed
// (file_changes will list modified files)

// 3. If needed, follow up with fixes
MCP({
  server: "codex-bridge",
  tool: "delegate_coding_task",
  arguments: {
    task_description: "Also add a unit test for the email validation schema",
    file_paths: ["app/routes/signup.tsx", "app/lib/validation.test.ts"]
  }
})
```
