---
date: 2026-04-22
topic: pi-issue-tracker-and-ask-user-question
---

# Pi issue tracker + AskUserQuestion tools

## What We're Building

Two new native Pi tools for the feature pipeline:

1. **Issue tracker** — a Pi-native, file-backed tracking tool for review findings, implementation tasks, and workflow follow-ups.
2. **AskUserQuestion** — a Pi-native interactive question tool that workflows can use whenever they need structured user input before continuing.

The issue tracker will use **JSON files in `.pi/issues/`** rather than markdown files in `todos/`. That keeps the storage shape tool-native, easier to validate, and simpler for structured reads/writes from agents and extensions.

These tools fill a concrete gap in the current repo: workflow prompts already refer to AskUserQuestion-style interactions and issue/todo tracking, but the Pi package does not yet provide first-class native tools for either capability.

## Why This Approach

Three realistic directions emerged:

### Approach A: Thin wrappers around current patterns

Add minimal tools that only cover the exact workflow references today.

**Pros:** fastest to ship, low risk.
**Cons:** likely to create another round of follow-up work when workflows need richer issue state or question behavior.

### Approach B: Native structured tools with focused scope **(chosen)**

Build:
- a JSON-backed issue tracker with core CRUD-style operations
- a single-question interactive AskUserQuestion tool with multiple-choice and freeform answers

**Pros:** enough structure for workflow automation, clean Pi-native design, matches extension patterns already in this repo.
**Cons:** slightly more upfront design than a minimal spike.

### Approach C: Full UI-heavy system from day one

Build the tools plus full TUI dashboards, review boards, and multi-step questionnaires.

**Pros:** polished and powerful.
**Cons:** over-scoped for the immediate gap; violates YAGNI.

We chose **Approach B** because it solves the actual missing primitives without prematurely committing to a large UI framework.

## Key Decisions

- **Issue storage:** JSON files in `.pi/issues/`.
  - Rationale: native structured storage, easy extension-side validation, repo-local state, clean separation from human-facing markdown docs.
- **Issue tracker scope (v1):** focused operations for workflow use.
  - Expected actions: `list`, `get`, `create`, `update`, `append_note`, `close`, `reopen`.
- **AskUserQuestion scope (v1):** single-question interactive tool.
  - Supports question text, optional multiple-choice options, optional freeform answer path, cancel handling, structured return payload.
- **Implementation surface:** new Pi extensions under `extensions/`.
  - Rationale: existing native tools live there and `package.json` already auto-loads `extensions/*.ts`.
- **Workflow compatibility:** these tools should map cleanly onto existing command/workflow language.
  - Rationale: current markdown workflows already instruct the agent to use AskUserQuestion and issue/todo tracking patterns.
- **State location:** project-local `.pi/issues/` committed-or-not depending on user workflow, but structurally local to the repo.
  - Rationale: keeps issue state tied to the project rather than global user machine state.

## Open Questions

- Final tool names:
  - `ask_user_question` vs `question` vs `questionnaire`
  - `issue_tracker` vs `issue` vs `todo`
- Exact issue schema:
  - likely fields: `id`, `title`, `status`, `priority`, `tags`, `created_at`, `updated_at`, `notes`, possibly `assignee_session`
- Whether to add a slash command or custom TUI browser in v1, or keep the first version tool-only.
- Whether issue IDs should be sequential (`ISSUE-001`) or random/stable (`8-char hex`).
- Whether closed issues should remain in the same directory or be archived separately.

## Next Steps

→ `/workflows:plan` for implementation details
