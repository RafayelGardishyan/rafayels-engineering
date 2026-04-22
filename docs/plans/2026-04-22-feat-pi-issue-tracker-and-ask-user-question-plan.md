---
date: 2026-04-22
type: feat
topic: pi-issue-tracker-and-ask-user-question
brainstorm: docs/brainstorms/2026-04-22-pi-issue-tracker-and-ask-user-question-brainstorm.md
status: draft
---

# ✨ feat: Pi-native issue tracker + AskUserQuestion tools

## Summary

Add two new native Pi extensions to support the feature pipeline directly inside this repo:

1. **`ask_user_question`** — an interactive user-input tool for single-question workflow pauses.
2. **`issue_tracker`** — a structured, JSON-backed issue tracking tool stored in `.pi/issues/`.

These tools close a real gap in the current package. Existing workflows repeatedly reference AskUserQuestion-style interaction and file/todo tracking, but the current Pi extension surface only ships config, memory, browser, figma, command aliasing, and output preprocessing.

## Motivation

The repository already contains workflow commands that assume two first-class capabilities exist:

- a way to stop and ask the user a structured question
- a way to record and manage implementation/review findings as persistent work items

Today, those ideas exist only in prompt text and in adjacent inspiration/examples. They are not first-class Pi-native tools in this repo.

Shipping them as native extensions improves:

- **workflow fidelity** — commands can rely on actual tools instead of aspirational prompt text
- **agent-native parity** — workflows gain user interaction and task tracking as direct primitives
- **future reuse** — other commands can use the same tools without inventing ad hoc patterns

## Context & Research Findings

### Existing repo patterns

- Native Pi tools are implemented in `extensions/*.ts` and auto-loaded via `package.json`.
- Current extensions are relatively self-contained and register tools directly with `pi.registerTool(...)`.
- This repo recently added compatibility-oriented extension behavior in `extensions/command-aliases.ts`, confirming extension-level workflow augmentation is an accepted pattern.
- Existing workflows under `commands/workflows/*.md` frequently reference **AskUserQuestion** and issue/todo management, but no matching native tool exists yet.

### Pi extension patterns

From Pi docs and examples:

- Interactive user input should use:
  - `ctx.ui.select()`
  - `ctx.ui.confirm()`
  - `ctx.ui.input()`
  - `ctx.ui.editor()`
  - or `ctx.ui.custom()` for richer custom UI
- The Pi examples already include:
  - `question.ts` for a single interactive question
  - `questionnaire.ts` for multi-question flows
  - `todo.ts` as a richer file-backed task manager reference pattern
- Extension tools can return structured text/details payloads and can optionally provide custom renderers.

### External inspiration

- `mitsuhiko/agent-stuff` `todos.ts` is a strong model for a file-backed issue manager with structured actions.
- `mitsuhiko/agent-stuff` `answer.ts` and Pi’s question examples validate that interactive question tools are a natural Pi extension capability.

## Recommendation

Implement both tools as focused, native Pi extensions with a deliberately modest v1 scope:

- **AskUserQuestion**: single-question interaction only
- **Issue tracker**: core structured issue lifecycle only

Do not build a large multi-screen TUI system in the first iteration. Keep the data model strong and the interaction model reliable.

## Detailed Design

### 1. `ask_user_question` tool

#### Purpose

Provide a first-class workflow primitive for asking the user a question and receiving a structured response.

#### Proposed API

```ts
ask_user_question({
  question: string,
  options?: Array<{
    value: string,
    label: string,
    description?: string,
  }>,
  allow_freeform?: boolean,
  placeholder?: string,
  required?: boolean,
})
```

#### Behavior

- If `options` are provided:
  - show a selection UI
  - optionally allow a freeform answer path when `allow_freeform` is true
- If no options are provided:
  - fall back to text input UI
- If the user cancels:
  - return a structured cancelled result, not an exception
- If `required` is true:
  - empty freeform submissions should reprompt or reject cleanly

#### Return shape

```json
{
  "status": "answered" | "cancelled",
  "question": "...",
  "answer": {
    "type": "option" | "freeform",
    "value": "...",
    "label": "..."
  }
}
```

#### Implementation notes

- Prefer starting from `ctx.ui.select()` / `ctx.ui.input()` for simplicity.
- If needed for polish, adapt the custom UI pattern from Pi example `question.ts`.
- Tool name should be explicit and workflow-friendly: **`ask_user_question`**.
  - This aligns better with existing workflow wording than a generic `question` name.

---

### 2. `issue_tracker` tool

#### Purpose

Track review findings, implementation tasks, and follow-up work in a structured repo-local format.

#### Storage model

Directory:

```text
.pi/issues/
```

Format:
- one JSON file per issue
- one optional metadata/index file only if needed later
- v1 should avoid premature indexing complexity if directory scan is sufficient

#### Issue file shape

```json
{
  "id": "ISSUE-001",
  "title": "Add AskUserQuestion tool to Pi package",
  "status": "open",
  "priority": "p2",
  "tags": ["workflow", "pi", "tooling"],
  "created_at": "2026-04-22T12:34:56Z",
  "updated_at": "2026-04-22T12:34:56Z",
  "notes": [
    {
      "created_at": "2026-04-22T12:34:56Z",
      "text": "Initial finding from review workflow"
    }
  ]
}
```

#### ID strategy

Use **sequential IDs** in v1:
- `ISSUE-001`
- `ISSUE-002`

Rationale:
- easier for humans to reference in prompts and PRs
- better fit for workflow output than opaque hashes
- sufficient for local file-backed storage

#### Proposed API

```ts
issue_tracker({ action: "list" | "get" | "create" | "update" | "append_note" | "close" | "reopen", ... })
```

Parameters by action:

- `list`
  - optional filters: `status`, `priority`, `tag`
- `get`
  - `id`
- `create`
  - `title`
  - optional `priority`, `tags`, `note`
- `update`
  - `id`
  - mutable fields: `title`, `priority`, `tags`
- `append_note`
  - `id`, `text`
- `close`
  - `id`
- `reopen`
  - `id`

#### Return shape

Consistent structured payloads:

```json
{
  "status": "ok",
  "action": "create",
  "issue": { ... }
}
```

or

```json
{
  "status": "ok",
  "action": "list",
  "issues": [ ... ]
}
```

#### Implementation notes

- Use `node:fs` / `node:fs/promises` and `node:path`.
- Ensure `.pi/issues/` exists on write paths.
- Keep read/write logic deterministic and small.
- Write pretty-printed JSON for inspectability.
- Use simple full-directory scans in v1; no separate index unless profiling shows need.

---

### 3. Workflow integration expectations

This PR should at minimum ship the tools themselves. If time allows, update workflow docs to reference the concrete native tool names.

Likely follow-up doc updates in this same PR:
- `commands/re/feature.md`
- `commands/workflows/brainstorm.md`
- `commands/workflows/plan.md`
- `commands/workflows/review.md`
- `commands/test-browser.md`
- `commands/test-xcode.md`

Goal:
- replace ambiguous “AskUserQuestion” wording with the actual tool name `ask_user_question`
- optionally replace generic issue/todo language where appropriate with `issue_tracker`

## Files to Create

```text
extensions/ask-user-question.ts
extensions/issue-tracker.ts
```

## Files to Modify

```text
README.md                         # document the two new Pi-native tools
commands/re/feature.md            # optional wording alignment
commands/workflows/brainstorm.md  # optional wording alignment
commands/workflows/plan.md        # optional wording alignment
commands/workflows/review.md      # optional wording alignment
```

## Implementation Plan

### Phase 1 — AskUserQuestion tool

- Create `extensions/ask-user-question.ts`
- Register `ask_user_question`
- Implement:
  - option selection path
  - freeform path
  - cancel handling
  - structured result payload
- Use Pi-native UI methods with minimal complexity

### Phase 2 — Issue tracker tool

- Create `extensions/issue-tracker.ts`
- Implement issue directory helpers:
  - ensure directory
  - compute next sequential id
  - read one issue
  - list issues
  - write issue atomically enough for local usage
- Register `issue_tracker`
- Implement actions:
  - `list`
  - `get`
  - `create`
  - `update`
  - `append_note`
  - `close`
  - `reopen`

### Phase 3 — Documentation alignment

- Update `README.md` to list both tools
- Optionally update command/workflow docs to use explicit tool names
- Keep wording backward-compatible where necessary

### Phase 4 — Validation

Manual validation checklist:

- `ask_user_question` with options only
- `ask_user_question` with freeform only
- `ask_user_question` with options + freeform
- `ask_user_question` cancel path
- `issue_tracker create`
- `issue_tracker list`
- `issue_tracker get`
- `issue_tracker update`
- `issue_tracker append_note`
- `issue_tracker close` / `reopen`
- verify files written under `.pi/issues/`

## Alternatives Considered

### Markdown-backed `todos/`

Rejected because the user explicitly chose JSON, and JSON is a better fit for extension-native structured storage.

### One monolithic extension for both tools

Possible, but rejected for clarity. Separate extension files better match the repo’s current organization and keep each tool focused.

### Rich custom TUI from day one

Rejected for v1 scope. Pi already provides simpler UI primitives that are enough to unblock workflows.

## Risks

- **Naming drift** — workflow docs say “AskUserQuestion” while tool ships as `ask_user_question`.
  - Mitigation: doc updates in same PR where practical.
- **Data races on issue ID generation** — simultaneous creates could collide.
  - Mitigation: acceptable in v1 for local interactive usage; if needed later, add a lightweight lock or index file.
- **Overbuilding UI** — custom TUI could increase complexity early.
  - Mitigation: start with built-in UI primitives first.

## Acceptance Criteria

- [ ] New extension `extensions/ask-user-question.ts` exists and registers `ask_user_question`
- [ ] `ask_user_question` supports multiple-choice selection
- [ ] `ask_user_question` supports freeform input
- [ ] `ask_user_question` returns structured cancellation state
- [ ] New extension `extensions/issue-tracker.ts` exists and registers `issue_tracker`
- [ ] `issue_tracker` stores issues as JSON files in `.pi/issues/`
- [ ] `issue_tracker` supports `list`, `get`, `create`, `update`, `append_note`, `close`, `reopen`
- [ ] Issue IDs are sequential and human-readable
- [ ] `README.md` documents both new Pi-native tools
- [ ] Manual validation passes for core happy paths

## Definition of Done

The repo ships two new Pi-native tools that the feature pipeline can rely on directly:

- user-interactive questioning via `ask_user_question`
- structured project-local issue tracking via `issue_tracker`

Both are documented, implemented in `extensions/`, and usable without any external MCP dependency.
