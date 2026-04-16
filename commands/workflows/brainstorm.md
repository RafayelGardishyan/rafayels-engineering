---
name: workflows:brainstorm
description: Explore requirements and approaches through collaborative dialogue before planning implementation
argument-hint: "[feature idea or problem to explore]"
---

# Brainstorm a Feature or Improvement

**Note: The current year is 2026.** Use this when dating brainstorm documents.

Brainstorming helps answer **WHAT** to build through collaborative dialogue. It precedes `/workflows:plan`, which answers **HOW** to build it.

**Process knowledge:** Load the `brainstorming` skill for detailed question techniques, approach exploration patterns, and YAGNI principles.

## Feature Description

<feature_description> #$ARGUMENTS </feature_description>

**If the feature description above is empty, ask the user:** "What would you like to explore? Please describe the feature, problem, or improvement you're thinking about."

Do not proceed until you have a feature description from the user.

## Execution Flow

### Phase 0: Assess Requirements Clarity

Evaluate whether brainstorming is needed based on the feature description.

**Clear requirements indicators:**
- Specific acceptance criteria provided
- Referenced existing patterns to follow
- Described exact expected behavior
- Constrained, well-defined scope

**If requirements are already clear:**
Use **AskUserQuestion tool** to suggest: "Your requirements seem detailed enough to proceed directly to planning. Should I run `/workflows:plan` instead, or would you like to explore the idea further?"

### Phase 0.1b: Task Classification

Determine if this is a software or non-software task.

**Software signals** (any 2+ = software):
- Keywords: implement, refactor, fix bug, API, endpoint, component, deploy, migrate, test, CI/CD
- References to files, repos, branches, PRs
- Mentions specific tech (React, SQL, Docker, etc.)

**Non-software signals** (absence of software signals + any 1):
- Keywords: plan, organize, schedule, budget, itinerary, strategy, proposal, curriculum, agenda
- Time-oriented language: dates, deadlines, durations
- People/logistics: venues, attendees, stakeholders, suppliers

**Classifier rule:** Check software signals first (high precision). Ambiguous cases default to software.

If non-software: load `references/universal-planning.md` and follow that workflow instead.

### Phase 0.5: Retrieve Relevant Cases from Memory

Before starting research, query the memory layer for relevant past brainstorm cases:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory query \
  "<feature description>" --phase brainstorm --k 3 --format md 2>/dev/null
```

- If the command returns markdown-formatted cases on stdout, include them in the phase context.
- If it exits with code 75 (memory unavailable) or returns nothing, continue without injection.
- Note any case_ids returned for cross-phase dedup and later signal emission.

### Phase 1: Understand the Idea

#### 1.1 Repository Research (Lightweight)

Run a quick repo scan to understand existing patterns. If Obsidian MCP tools are available, also dispatch the vault-researcher in parallel:

- Task repo-research-analyst("Understand existing patterns related to: <feature_description>")
- Task vault-researcher("Search vault for decisions and context related to: <feature_description>") — conditional: only if obsidian-adr or obsidian MCP is available

Focus on: similar features, established patterns, CLAUDE.md guidance.

#### 1.2 Collaborative Dialogue

Use the **AskUserQuestion tool** to ask questions **one at a time**.

**Guidelines (see `brainstorming` skill for detailed techniques):**
- Prefer multiple choice when natural options exist
- Start broad (purpose, users) then narrow (constraints, edge cases)
- Validate assumptions explicitly
- Ask about success criteria

**Exit condition:** Continue until the idea is clear OR user says "proceed"

### Phase 2: Explore Approaches

Propose **2-3 concrete approaches** based on research and conversation.

For each approach, provide:
- Brief description (2-3 sentences)
- Pros and cons
- When it's best suited

Lead with your recommendation and explain why. Apply YAGNI—prefer simpler solutions.

Use **AskUserQuestion tool** to ask which approach the user prefers.

### Phase 3: Capture the Design

Write a brainstorm document to `docs/brainstorms/YYYY-MM-DD-<topic>-brainstorm.md`.

**Document structure:** Load `references/brainstorm-phase3.md` for the template format.

Ensure `docs/brainstorms/` directory exists before writing.

### Phase 3.5: Mandatory Document Review

Run structured review on the brainstorm document before handoff:

Load the `document-review` skill and apply it to the brainstorm document just written.
This is automatic — do not ask for permission.

### Phase 3.6: Capture Case to Memory

After the brainstorm document is written and reviewed, capture it as a case:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory write \
  --phase brainstorm \
  --type decision \
  --query "<feature description>" \
  --title "<short brainstorm title>" \
  --plan "<chosen approach summary>" \
  --outcome "<brainstorm document path>" \
  --tags '["brainstorm"]' \
  --json 2>/dev/null
```

Capture the returned `case_id` for signal emission in Phase 4.

### Phase 3.7: Emit Approval Signal

If the user approved the brainstorm (selected "Proceed to planning"), emit a positive signal:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory signal \
  <case_id> approval 1.0 --source "phase:brainstorm" 2>/dev/null
```

If they requested substantial rework, emit a mildly negative signal instead:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory signal \
  <case_id> approval -0.3 --source "phase:brainstorm-rework" 2>/dev/null
```

### Phase 4: Handoff

Use **AskUserQuestion tool** to present next steps:

**Question:** "Brainstorm captured. What would you like to do next?"

**Options:**
1. **Review and refine** - Improve the document through structured self-review
2. **Proceed to planning** - Run `/workflows:plan` (will auto-detect this brainstorm)
3. **Done for now** - Return later

**If user selects "Review and refine":**

Load the `document-review` skill and apply it to the brainstorm document.

When document-review returns "Review complete", present next steps:

1. **Move to planning** - Continue to `/workflows:plan` with this document
2. **Done for now** - Brainstorming complete. To start planning later: `/workflows:plan [document-path]`

## Output Summary

When complete, display:

```
Brainstorm complete!

Document: docs/brainstorms/YYYY-MM-DD-<topic>-brainstorm.md

Key decisions:
- [Decision 1]
- [Decision 2]

Next: Run `/workflows:plan` when ready to implement.
```

## Important Guidelines

- **Stay focused on WHAT, not HOW** - Implementation details belong in the plan
- **Ask one question at a time** - Don't overwhelm
- **Apply YAGNI** - Prefer simpler approaches
- **Keep outputs concise** - 200-300 words per section max

NEVER CODE! Just explore and document decisions.
