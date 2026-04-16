---
name: re:feature
description: End-to-end feature pipeline — from idea to merged PR with documentation updates. Orchestrates brainstorm, plan, work, review, and compound workflows.
argument-hint: "[optional: feature idea or description]"
---

# Feature Pipeline

**Note: The current year is 2026.** Use this when dating documents.

Orchestrate the full feature lifecycle: gather context, brainstorm, plan, implement in a worktree, create a PR, review, compound knowledge, and update documentation.

## Feature Description

<feature_description> #$ARGUMENTS </feature_description>

## Execution Flow

### Phase -1: Select Strategy

Before executing any phases, select a workflow strategy.

1. **Discover available strategies**: List all `.md` files in `references/strategies/`:
   ```bash
   ls references/strategies/*.md 2>/dev/null
   ```

2. **Check for `--strategy` argument**: If the user passed `--strategy=<name>`, load that strategy file directly.

3. **If no strategy specified, ask the user**:
   Read the "When to Use" section of each discovered strategy file. Present them via AskUserQuestion:

   ```
   "Which workflow strategy should we use?"
   - Full Process (Recommended) — Complete pipeline: brainstorm → plan → work → review → compound → docs
   - Quick Spike — Fast prototype: skip brainstorm, lightweight plan, minimal review
   - Security First — Maximum rigor: threat modeling, all security reviewers, no auto-merge
   - Review Only — Audit existing code: skip implementation, run all reviewers
   ```

4. **Load the selected strategy file** and read it as natural-language guidance. Before each subsequent phase:
   - If the strategy sets `enabled: false` for that phase → skip the phase entirely
   - If the strategy provides `guidance:` text → follow that guidance
   - If the phase is not mentioned in the strategy → use default behavior

5. **Composition**: If the strategy has `base: <other-strategy>`, load that base strategy first and merge. The overlay's phase keys replace base keys per-phase; everything else inherits.

### Phase 0: Gather Project Context

Before anything else, understand the project landscape.

<parallel_tasks>

1. **Documentation scan**: Read project documentation to understand architecture, conventions, and constraints.
   ```bash
   find docs/ -name "*.md" -type f 2>/dev/null | head -20
   cat README.md 2>/dev/null
   cat CLAUDE.md 2>/dev/null
   ```

2. **Vault research** (conditional): If obsidian-adr or obsidian MCP tools are available, dispatch the vault-researcher agent in parallel with documentation scan.
   - Task vault-researcher("Search vault for context related to: <feature_description>")
   - If no Obsidian MCP available, this step is skipped silently (zero cost)

3. **Dev logs**: Check recent dev logs for context on recent work and decisions.
   ```bash
   skill: dev-log
   ```
   Review the last 5 dev log entries to understand recent changes and ongoing work.

3. **ADR search**: Query Architecture Decision Records for relevant past decisions.
   ```bash
   skill: using-adr-plugin
   ```
   Run semantic searches related to the feature area. Read full ADRs for any relevant hits. Traverse the graph for connected decisions.

</parallel_tasks>

**Synthesize context**: Summarize key findings that will inform the feature:
- Relevant architectural decisions and constraints
- Recent related work from dev logs
- Existing patterns and conventions
- Any blockers or dependencies to be aware of

### Phase 1: Understand the Feature

**If the feature description above is empty**, use AskUserQuestion:
"What feature would you like to implement? Describe the problem you're solving or the functionality you want to add."

Do not proceed until you have a clear feature description.

**Present context summary** to the user:
"Based on project research, here's what I found relevant to this feature: [summary]. Does this align with your understanding? Anything to add?"

### Phase 2: Create Worktree

Set up an isolated workspace for this feature.

```bash
skill: git-worktree
```

Create a new worktree with a meaningful branch name derived from the feature description (e.g., `feat/user-authentication-flow`).

**Important**: All subsequent work happens in this worktree. Ensure you're operating in the worktree directory.

### Phase 3: Brainstorm

Run the brainstorming workflow to explore requirements and approaches.

```bash
/workflows:brainstorm <feature_description_with_context>
```

Pass the feature description along with the synthesized project context from Phase 0.

**Wait for the user to refine the brainstorm.** The brainstorm workflow includes iterative refinement. When the user selects "Proceed to planning" or indicates they're satisfied with the brainstorm, automatically continue to Phase 4.

**Auto-transition trigger**: When `/workflows:brainstorm` completes and the user approves the brainstorm document, proceed immediately to Phase 4 without asking.

### Phase 4: Plan

Run the planning workflow, which will auto-detect the brainstorm document.

```bash
/workflows:plan <feature_description>
```

The plan workflow will:
- Find the brainstorm document from Phase 3
- Conduct research (local + conditional external)
- Create a structured plan in `docs/plans/`
- Offer deepening and review options

**Wait for the user to refine the plan.** When the user selects "Start /workflows:work" or indicates the plan is ready, automatically continue to Phase 5.

**Auto-transition trigger**: When the user finishes deepening/reviewing the plan, proceed to Phase 5 without asking.

### Phase 5: Implement

Execute the plan in the worktree.

```bash
/workflows:work <path_to_plan_file>
```

The work workflow will:
- Break the plan into tasks
- Implement with incremental commits
- Run tests continuously
- Follow existing patterns

**Important**: The work workflow handles its own PR creation. However, intercept before PR creation to ensure:
1. All commits are in the worktree branch
2. The branch is pushed to remote

### Phase 6: Push & Create PR

After implementation is complete:

```bash
# Ensure all changes are committed
git status

# Push the worktree branch
git push -u origin <branch-name>

# Create PR (if not already created by /workflows:work)
gh pr create --title "<type>: <feature title>" --body "$(cat <<'EOF'
## Summary
- <what was built>
- <why it was needed>

## Context
- Brainstorm: docs/brainstorms/<brainstorm-file>.md
- Plan: docs/plans/<plan-file>.md

## Testing
- <tests added/modified>
- <manual testing performed>

---

[![Rafayel Engineered](https://img.shields.io/badge/Rafayel-Engineered-6366f1)](https://github.com/rgardishyan) Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### Phase 7: Review & Compound

Run review and compound workflows in parallel on the PR.

<parallel_tasks>

1. **Code Review**:
   ```bash
   /workflows:review <PR-number>
   ```
   This runs multi-agent analysis and creates findings as todos.

2. **Compound Knowledge**:
   ```bash
   /workflows:compound "Implemented <feature_description>"
   ```
   This documents solutions and learnings from the implementation.

</parallel_tasks>

### Phase 8: Address Review Findings

After review and compound complete:

1. **Incorporate review findings**: Address any P1 (critical) issues immediately. Triage P2/P3 findings.
2. **Push solutions from compound**: If compound generated any code improvements, incorporate them.
3. **Push fixes**:
   ```bash
   git add -A
   git commit -m "$(cat <<'EOF'
   fix: address code review findings

   - <finding 1 addressed>
   - <finding 2 addressed>

   Co-Authored-By: Claude <noreply@anthropic.com>
   EOF
   )"
   git push
   ```

### Phase 9: Automerge & Documentation

1. **Set PR to automerge**:
   ```bash
   gh pr merge <PR-number> --auto --squash
   ```

2. **Update documentation** in parallel:

<parallel_tasks>

   a. **Dev Log**: Create a dev log entry documenting this feature.
      ```bash
      skill: dev-log
      ```
      Include: PR link, what changed, key decisions, screenshots if UI work.

   b. **ADRs**: If architectural decisions were made during implementation, record them.
      ```bash
      skill: using-adr-plugin
      ```
      Create new ADRs for significant decisions. Link to related existing ADRs.

   c. **Project docs**: Update any project documentation affected by this feature (README, API docs, etc.).

</parallel_tasks>

### Phase 10: Cleanup

1. **Clean up worktree** after merge:
   ```bash
   skill: git-worktree
   # Use the skill to remove the worktree
   ```

2. **Emit final merge signal to memory** (if cases were written during the run):

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory signal \
     <work_case_id> merge 1.0 --source "pr:<PR number>" 2>/dev/null
   ```

   This closes the feedback loop — the successful merge retroactively upgrades the
   work phase case's reward, making it more likely to be retrieved in future runs.

3. **Offer memory review (optional)**:

   Ask the user via AskUserQuestion: "Want to run /re:memory-review to inspect
   the case bank from this run and check for emerging patterns?" Options:
   - **Yes** — invoke `/re:memory-review`
   - **No** — skip, continue to summary

4. **Summary**: Present final status to user:
   ```
   Feature Pipeline Complete!

   PR: <PR-URL> (automerge enabled)
   Branch: <branch-name>
   Brainstorm: docs/brainstorms/<file>.md
   Plan: docs/plans/<file>.md
   Solutions: docs/solutions/<file>.md (if created)
   Dev Log: Updated
   ADRs: <new ADRs created, if any>

   All documentation updated. Worktree cleaned up.
   ```

## Key Principles

- **Context first**: Always gather project context before starting
- **User in the loop**: Wait for user approval at brainstorm and plan phases
- **Auto-transition**: Move to next phase automatically once user approves
- **Isolated work**: Use worktrees to keep main branch clean
- **Document everything**: Dev logs, ADRs, and compound docs capture knowledge
- **Ship complete**: Don't stop at PR creation — review, fix, merge, document

## Error Recovery

- If any phase fails, present the error and ask the user how to proceed
- If the worktree gets into a bad state, offer to recreate it
- If tests fail during work, fix them before proceeding
- If review finds P1 issues, they MUST be addressed before automerge
